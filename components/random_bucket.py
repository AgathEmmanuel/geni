# components/batch_buckets.py
from utils.base import load_template, render_template, write_output, write_hcl2json
from utils.configure import replace_key
from pathlib import Path


def generate(parameters, name, data, templates_dir, compiled_path):
    template_path = templates_dir / "terraform_tf/bucket.tf"

    template_path = write_hcl2json(template_path) or template_path

    template = load_template(template_path)
    
    no_of_buckets = parameters.get("no_of_buckets", 1)
    location = parameters.get("location")
    project = data.get("project")
    compiled_path = Path(compiled_path)

    for i in range(1, no_of_buckets + 1):
        bucket_name = f"test-bucket-azadsf-{i}"
        param = {
            "bucket_name": bucket_name,
            "location": location,
            "project": project
        }
        rendered = render_template(template, param, data)
        #rendered = replace_key(rendered, "bucket_test", bucket_name)


        tf_bucket_dict = rendered["resource"][0]["google_storage_bucket"][0]
        # Extract the value of the existing key
        value = tf_bucket_dict.pop("bucket_test")  # remove the old key
        # Insert with the new key
        tf_bucket_dict[bucket_name] = value


        write_output(template_path, compiled_path, rendered, name)
