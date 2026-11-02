data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_region" "current" {}

locals {
  azs              = slice(data.aws_availability_zones.available.names, 0, var.az_count)
  needs_public     = var.nat != "none"
  endpoint_subnets = slice(aws_subnet.private[*].id, 0, var.interface_endpoint_az_count)
}

resource "aws_vpc" "this" {
  cidr_block           = var.cidr_block
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = var.name }
}

resource "aws_subnet" "private" {
  count             = var.az_count
  vpc_id            = aws_vpc.this.id
  cidr_block        = cidrsubnet(var.cidr_block, 4, count.index)
  availability_zone = local.azs[count.index]
  tags              = { Name = "${var.name}-private-${local.azs[count.index]}", tier = "private" }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.name}-private" }
}

resource "aws_route_table_association" "private" {
  count          = var.az_count
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# --- public side, only when egress is needed -----------------------------------
resource "aws_internet_gateway" "this" {
  count  = local.needs_public ? 1 : 0
  vpc_id = aws_vpc.this.id
  tags   = { Name = var.name }
}

resource "aws_subnet" "public" {
  count                   = local.needs_public ? 1 : 0
  vpc_id                  = aws_vpc.this.id
  cidr_block              = cidrsubnet(var.cidr_block, 4, 15)
  availability_zone       = local.azs[0]
  map_public_ip_on_launch = false
  tags                    = { Name = "${var.name}-public-${local.azs[0]}", tier = "public" }
}

resource "aws_route_table" "public" {
  count  = local.needs_public ? 1 : 0
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this[0].id
  }
  tags = { Name = "${var.name}-public" }
}

resource "aws_route_table_association" "public" {
  count          = local.needs_public ? 1 : 0
  subnet_id      = aws_subnet.public[0].id
  route_table_id = aws_route_table.public[0].id
}

# --- gateway endpoints (free) -------------------------------------------------
resource "aws_vpc_endpoint" "gateway" {
  for_each          = toset(["s3", "dynamodb"])
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${data.aws_region.current.region}.${each.key}"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]
  tags              = { Name = "${var.name}-${each.key}" }
}

# --- interface endpoints --------------------------------------------------------
resource "aws_security_group" "endpoints" {
  name        = "${var.name}-vpc-endpoints"
  description = "HTTPS from inside the VPC to interface endpoints"
  vpc_id      = aws_vpc.this.id

  ingress {
    description = "HTTPS from VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.cidr_block]
  }
}

resource "aws_vpc_endpoint" "interface" {
  for_each            = toset(var.interface_endpoints)
  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${data.aws_region.current.region}.${each.key}"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = local.endpoint_subnets
  security_group_ids  = [aws_security_group.endpoints.id]
  private_dns_enabled = true
  tags                = { Name = "${var.name}-${each.key}" }
}

# --- Lambda security group (shared by in-VPC Lambdas) -------------------------
resource "aws_security_group" "lambda" {
  name        = "${var.name}-lambda"
  description = "In-VPC Lambdas; egress only"
  vpc_id      = aws_vpc.this.id

  egress {
    description = "All egress (RDS, endpoints, NAT)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
