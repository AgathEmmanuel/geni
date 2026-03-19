terraform {
  backend "s3" {
    bucket         = "${{ bucket }}"
    key            = "${{ key }}"
    region         = "${{ region }}"
    dynamodb_table = "${{ dynamodb_table }}"
    encrypt        = true
  }
}
