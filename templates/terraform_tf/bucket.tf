# Resources
resource "google_storage_bucket" "bucket_test" {
  name     = "__bucket_name__"
  location = "US"
  uniform_bucket_level_access = true
  force_destroy               = false
  public_access_prevention    = "enforced"
  versioning {
    enabled = true
  }
}