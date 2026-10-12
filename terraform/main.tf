terraform {
  required_version = ">= 1.5"
  required_providers {
    aws  = { source = "hashicorp/aws", version = "~> 5.0" }
    time = { source = "hashicorp/time", version = "~> 0.11" }
  }
}

variable "region" {
  type    = string
  default = "ap-south-1"
}
variable "app_name" {
  type    = string
  default = "deployguard"
}
variable "env_name" {
  type    = string
  default = "deployguard-prod"
}
variable "instance_type" {
  type    = string
  default = "t3.micro"
}
variable "github_repo" {
  type    = string
  default = "ojaslan/deploy-guard"
}
variable "groq_model" {
  type    = string
  default = "openai/gpt-oss-120b"
}
variable "create_github_oidc_provider" {
  type        = bool
  default     = true
  description = "Set false if the GitHub OIDC provider already exists in this account."
}
variable "groq_api_key" {
  type      = string
  sensitive = true
}

provider "aws" {
  region = var.region
}

data "aws_elastic_beanstalk_solution_stack" "docker" {
  most_recent = true
  name_regex  = "^64bit Amazon Linux 2023 (.*) running Docker$"
}

# ---------- Elastic Beanstalk roles ----------
resource "aws_iam_role" "ec2" {
  name = "deployguard-eb-ec2-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ec2_web" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AWSElasticBeanstalkWebTier"
}
resource "aws_iam_role_policy_attachment" "ec2_worker" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AWSElasticBeanstalkWorkerTier"
}
# Read-only, for /metrics/live. Remove this block if you do not want live metrics.
resource "aws_iam_role_policy_attachment" "ec2_cloudwatch_read" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchReadOnlyAccess"
}

resource "aws_iam_instance_profile" "ec2" {
  name = "deployguard-eb-ec2-profile"
  role = aws_iam_role.ec2.name
}

resource "aws_iam_role" "service" {
  name = "deployguard-eb-service-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "elasticbeanstalk.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = { StringEquals = { "sts:ExternalId" = "elasticbeanstalk" } }
    }]
  })
}
resource "aws_iam_role_policy_attachment" "service_health" {
  role       = aws_iam_role.service.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSElasticBeanstalkEnhancedHealth"
}
resource "aws_iam_role_policy_attachment" "service_updates" {
  role       = aws_iam_role.service.name
  policy_arn = "arn:aws:iam::aws:policy/AWSElasticBeanstalkManagedUpdatesCustomerRolePolicy"
}

# IAM changes need a moment to propagate before Elastic Beanstalk can use them.
resource "time_sleep" "iam_propagation" {
  create_duration = "30s"
  depends_on = [
    aws_iam_instance_profile.ec2,
    aws_iam_role_policy_attachment.ec2_web,
    aws_iam_role_policy_attachment.ec2_worker,
    aws_iam_role_policy_attachment.service_health,
    aws_iam_role_policy_attachment.service_updates,
  ]
}

# ---------- Application + environment (starts with the sample app; CI/CD deploys the real one) ----------
resource "aws_elastic_beanstalk_application" "app" {
  name = var.app_name
}

resource "aws_elastic_beanstalk_environment" "env" {
  name                = var.env_name
  application         = aws_elastic_beanstalk_application.app.name
  solution_stack_name = data.aws_elastic_beanstalk_solution_stack.docker.name
  depends_on          = [time_sleep.iam_propagation]

  setting {
    namespace = "aws:elasticbeanstalk:environment"
    name      = "EnvironmentType"
    value     = "SingleInstance"
  }
  setting {
    namespace = "aws:elasticbeanstalk:environment"
    name      = "ServiceRole"
    value     = aws_iam_role.service.arn
  }
  setting {
    namespace = "aws:autoscaling:launchconfiguration"
    name      = "IamInstanceProfile"
    value     = aws_iam_instance_profile.ec2.name
  }
  setting {
    namespace = "aws:ec2:instances"
    name      = "InstanceTypes"
    value     = var.instance_type
  }
  setting {
    namespace = "aws:elasticbeanstalk:healthreporting:system"
    name      = "SystemType"
    value     = "enhanced"
  }

  setting {
    namespace = "aws:elasticbeanstalk:application:environment"
    name      = "GROQ_API_KEY"
    value     = var.groq_api_key
  }
  setting {
    namespace = "aws:elasticbeanstalk:application:environment"
    name      = "GROQ_MODEL"
    value     = var.groq_model
  }
  setting {
    namespace = "aws:elasticbeanstalk:application:environment"
    name      = "AWS_REGION"
    value     = var.region
  }
  setting {
    namespace = "aws:elasticbeanstalk:application:environment"
    name      = "EB_ENVIRONMENT_NAME"
    value     = var.env_name
  }
  setting {
    namespace = "aws:elasticbeanstalk:application:environment"
    name      = "DG_DIAG_RATE_PER_MIN"
    value     = "10"
  }

  lifecycle {
    ignore_changes = [version_label]
  }
}

# ---------- GitHub Actions -> AWS (OIDC, no stored keys) ----------
resource "aws_iam_openid_connect_provider" "github" {
  count           = var.create_github_oidc_provider ? 1 : 0
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

data "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 0 : 1
  url   = "https://token.actions.githubusercontent.com"
}

locals {
  oidc_arn = var.create_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : data.aws_iam_openid_connect_provider.github[0].arn
}

resource "aws_iam_role" "github" {
  name = "deployguard-github-deploy"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = local.oidc_arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = { "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com" }
        StringLike   = { "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:*" }
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "github_eb" {
  role       = aws_iam_role.github.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess-AWSElasticBeanstalk"
}

output "url" {
  value = "http://${aws_elastic_beanstalk_environment.env.cname}"
}
output "github_role_arn" {
  value = aws_iam_role.github.arn
}
