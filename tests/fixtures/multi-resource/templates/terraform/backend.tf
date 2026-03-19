terraform {
  backend "gcs" {
    bucket = "${{ bucket_name }}"
    prefix = "${{ tfstate_prefix }}"
  }
}
