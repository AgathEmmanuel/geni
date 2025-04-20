resource "google_project_service" "__service_name_key__" {
  project = "__project_name__"
  service = "__service_name__"
  

  #service = "compute.googleapis.com"

  #timeouts {
  #  create = "30m"
  #  update = "40m"
  #}

  #disable_on_destroy = false

}


#resource "google_project_service" "__service_name2__" {
#  project = "__project_id__"
#  service = "__service_name2__"
  

  #service = "compute.googleapis.com"

  #timeouts {
  #  create = "30m"
  #  update = "40m"
  #}

  #disable_on_destroy = false
#}