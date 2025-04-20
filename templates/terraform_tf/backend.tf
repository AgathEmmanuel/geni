terraform {
  backend "gcs" {
    bucket = "__bucket_name__"
    prefix = "__tfstate_prefix__"
  }
}
