from geni.template import Template, TerraformHCL, RenderContext


class RedisTemplate(Template):
    """Generate Memorystore Redis instances using render_static.

    Demonstrates the render_static feature: a Python template that loops
    over a list of Redis instances and renders a static HCL template for
    each one, combining them into a single output file.
    """

    def render(self, context: RenderContext):
        p = context.params
        blocks = []

        for instance in p["instances"]:
            name = instance["name"]
            resource_name = name.replace("-", "_")

            hcl = context.render_static("terraform/redis.tf", {
                "resource_name": resource_name,
                "instance_name": f"{p['project']}-{p['environment']}-{name}",
                "project": p["project"],
                "region": p["region"],
                "tier": instance.get("tier", p.get("default_tier", "BASIC")),
                "memory_size_gb": instance.get("memory_size_gb", 1),
                "redis_version": instance.get("redis_version", "REDIS_7_0"),
                "display_name": f"{p['environment']}-{name}",
                "network_name": p["network_name"],
                "environment": p["environment"],
                "maxmemory_policy": instance.get("maxmemory_policy", "allkeys-lru"),
            })
            blocks.append(hcl)

        return TerraformHCL("redis.tf", "\n".join(blocks))
