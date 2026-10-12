# Terraform (infrastructure as code)

Creates: Elastic Beanstalk application + Docker environment (single instance), its IAM roles,
the GitHub OIDC provider and the `deployguard-github-deploy` role used by GitHub Actions.
The environment starts with the sample app; the CI/CD pipeline deploys the real image.

Run it from AWS CloudShell (console login, no access keys):
```
git clone https://github.com/ojaslan/deploy-guard.git && cd deploy-guard/terraform
read -s -p "Groq key: " TF_VAR_groq_api_key; export TF_VAR_groq_api_key; echo
terraform init && terraform plan && terraform apply
```
Outputs: `url` (the site) and `github_role_arn` (set it as the GitHub repo variable `AWS_ROLE_ARN`).
Tear down: `terraform destroy`.

Notes: the Groq key is stored in plain text in the state file. Keep `terraform.tfstate` private (it is git-ignored).
If the OIDC provider already exists: `terraform apply -var create_github_oidc_provider=false`.
