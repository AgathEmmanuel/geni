# components/batch_buckets.py
from utils.base import load_template, render_template, write_output, write_hcl2json
from utils.configure import replace_key, deep_merge_dicts
from pathlib import Path


def generate(parameters, name, data, templates_dir, compiled_path):
    base_template_path = templates_dir / "terraform_tf/service.tf"

    template_path = write_hcl2json(base_template_path)

    template = load_template(template_path)

    services = parameters.get("services")
    project = data.get("project")

    compiled_path = Path(compiled_path)

    rendered_final = {}
    for i in services:
        
        param = {
            "service_name": i,
            "service_name_key": i.replace(".", "_")+"_key",
            "project_name": project
        }
        rendered = render_template(template, param, data)
        rendered_final = deep_merge_dicts(rendered_final, rendered)

    write_output(template_path, compiled_path, rendered_final, name)
