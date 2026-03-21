resource "google_redis_instance" "${{ resource_name }}" {
  name               = "${{ instance_name }}"
  project            = "${{ project }}"
  region             = "${{ region }}"
  tier               = "${{ tier }}"
  memory_size_gb     = ${{ memory_size_gb }}
  redis_version      = "${{ redis_version }}"
  display_name       = "${{ display_name }}"
  authorized_network = "projects/${{ project }}/global/networks/${{ network_name }}"

  redis_configs = {
    maxmemory-policy = "${{ maxmemory_policy }}"
  }

  labels = {
    environment = "${{ environment }}"
    managed-by  = "geni"
  }
}
