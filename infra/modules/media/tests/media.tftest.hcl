mock_provider "aws" {
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
  mock_resource "aws_s3_bucket" {
    defaults = { arn = "arn:aws:s3:::localbini-dev-media", bucket_regional_domain_name = "localbini-dev-media.s3.eu-central-1.amazonaws.com" }
  }
  mock_resource "aws_cloudfront_distribution" {
    defaults = { arn = "arn:aws:cloudfront::123456789012:distribution/EDFDVBD6EXAMPLE", domain_name = "d111.cloudfront.net" }
  }
}

variables {
  name               = "localbini-dev"
  cors_allow_origins = ["http://localhost:5173"]
}

run "bucket_is_private_and_served_through_oac" {
  command = apply

  assert {
    condition = alltrue([
      aws_s3_bucket_public_access_block.media.block_public_acls,
      aws_s3_bucket_public_access_block.media.block_public_policy,
      aws_s3_bucket_public_access_block.media.ignore_public_acls,
      aws_s3_bucket_public_access_block.media.restrict_public_buckets,
    ])
    error_message = "all public access must be blocked"
  }
  assert {
    condition     = aws_s3_bucket.media.bucket == "localbini-dev-media"
    error_message = "bucket must be env-prefixed (deploy role / boundary scoping)"
  }
  assert {
    condition     = aws_cloudfront_origin_access_control.media.signing_behavior == "always"
    error_message = "CloudFront must sign every origin request (OAC)"
  }
  assert {
    condition     = aws_cloudfront_distribution.media.default_cache_behavior[0].viewer_protocol_policy == "redirect-to-https"
    error_message = "HTTPS only"
  }
  assert {
    condition     = output.cdn_domain == "d111.cloudfront.net"
    error_message = "CDN domain is exported for the API"
  }
}
