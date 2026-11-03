# --- NAT Gateway (prod) ------------------------------------------------------
resource "aws_eip" "nat" {
  count  = var.nat == "gateway" ? 1 : 0
  domain = "vpc"
  tags   = { Name = "${var.name}-nat" }
}

resource "aws_nat_gateway" "this" {
  count         = var.nat == "gateway" ? 1 : 0
  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.public[0].id
  tags          = { Name = var.name }
}

resource "aws_route" "private_nat_gateway" {
  count                  = var.nat == "gateway" ? 1 : 0
  route_table_id         = aws_route_table.private.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.this[0].id
}

# --- NAT instance (dev): t4g.nano, Amazon Linux 2023, iptables masquerade ------
data "aws_ssm_parameter" "al2023_arm64" {
  count = var.nat == "instance" ? 1 : 0
  name  = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64"
}

resource "aws_security_group" "nat" {
  count       = var.nat == "instance" ? 1 : 0
  name        = "${var.name}-nat-instance"
  description = "NAT instance: accept traffic from private subnets"
  vpc_id      = aws_vpc.this.id

  ingress {
    description = "From VPC"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [var.cidr_block]
  }

  egress {
    description = "To internet"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "nat" {
  count                       = var.nat == "instance" ? 1 : 0
  ami                         = data.aws_ssm_parameter.al2023_arm64[0].value
  instance_type               = "t4g.nano"
  subnet_id                   = aws_subnet.public[0].id
  associate_public_ip_address = true
  source_dest_check           = false
  vpc_security_group_ids      = [aws_security_group.nat[0].id]

  metadata_options {
    http_tokens = "required"
  }

  root_block_device {
    encrypted   = true
    volume_size = 8
  }

  # User data only runs on first boot: replace the instance when the script changes.
  user_data_replace_on_change = true
  user_data                   = <<-EOT
    #!/bin/bash
    set -euo pipefail
    # A t4g.nano has 512 MB; dnf's repo metadata alone got it OOM-killed (#41).
    fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    for attempt in 1 2 3; do
      dnf install -y --setopt=install_weak_deps=False iptables-services && break
      [ "$attempt" = 3 ] && exit 1
      sleep 10
    done
    echo 'net.ipv4.ip_forward = 1' > /etc/sysctl.d/90-nat.conf
    sysctl --system
    IFACE=$(ip route | awk '/default/ {print $5; exit}')
    iptables -t nat -A POSTROUTING -o "$IFACE" -s ${var.cidr_block} -j MASQUERADE
    iptables -F FORWARD
    iptables-save > /etc/sysconfig/iptables # what `service iptables save` does, without initscripts
    systemctl enable --now iptables
  EOT

  tags = { Name = "${var.name}-nat" }

  lifecycle {
    ignore_changes = [ami]
  }
}

# A fixed public IP, so external services (e.g. a database allowlist) can trust
# this NAT across instance stop/start or replacement. Same price as the
# auto-assigned public IPv4 it replaces.
resource "aws_eip" "nat_instance" {
  count    = var.nat == "instance" ? 1 : 0
  domain   = "vpc"
  instance = aws_instance.nat[0].id
  tags     = { Name = "${var.name}-nat-instance" }
}

resource "aws_route" "private_nat_instance" {
  count                  = var.nat == "instance" ? 1 : 0
  route_table_id         = aws_route_table.private.id
  destination_cidr_block = "0.0.0.0/0"
  network_interface_id   = aws_instance.nat[0].primary_network_interface_id
}
