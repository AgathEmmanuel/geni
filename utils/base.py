import os
import re
import json
import tempfile
import yaml
import copy
import subprocess  # Add at the top with other imports
import importlib.util
from pathlib import Path


def write_hcl2json(template_path):
    """
    Convert HCL2 file to JSON format using hcl2json command line tool.
    """
    # For .tf template files
    if str(template_path).endswith(".tf"):
        tf_json_path = Path("templates/terraform_tf_json") / (template_path.stem + ".tf.json")
        tf_json_path.parent.mkdir(parents=True, exist_ok=True)
    
        print(f"[~] Converting {template_path} to {tf_json_path}")

        # Only regenerate if the input is newer or output doesn't exist
        if not tf_json_path.exists() or template_path.stat().st_mtime > tf_json_path.stat().st_mtime:
            print(f"[~] Converting {template_path} → {tf_json_path} using hcl2json")
            cmd = f"hcl2json"
            
            try:
                with open(template_path, 'r') as input_file, open(tf_json_path, 'w') as output_file:
                    result = subprocess.run(
                        cmd.split(),
                        stdin=input_file,
                        stdout=output_file,
                        stderr=subprocess.PIPE,
                        timeout=10
                    )
                if result.returncode == 0:
                    print(f"[~] Successfully converted {template_path} to {tf_json_path}")
                else:
                    print(f"[!] Conversion failed with return code {result.returncode}")
            except subprocess.CalledProcessError as e:
                print(f"[!] Error converting {template_path}:\n{e.stderr.decode().strip()}")
                return
            except subprocess.TimeoutExpired:
                print(f"[!] Timeout while converting {template_path}")
                return
    
        # Now switch template_path to the generated tf.json
        return tf_json_path

def load_template(path):
    with open(path) as f:
        if str(path).endswith(".json"):
            return json.load(f)

        elif str(path).endswith((".yaml", ".yml")):
            try:
                return yaml.safe_load(f)  # Try loading as single YAML document
            except yaml.YAMLError:
                # If it fails, try loading as multiple documents
                with open(path) as f2:
                    return list(yaml.safe_load_all(f2))

    raise ValueError(f"Unsupported file type: {path}")
    
def resolve(val, data):
    if isinstance(val, str) and val.startswith("data."):
        _, key = val.split(".", 1)
        return data.get(key)
    return val

def render_template(template, parameters, data):
    def substitute(value):
        if isinstance(value, str):
            def replace(match):
                key = match.group(1)
                resolved = resolve(parameters.get(key, f"__{key}__"), data)
                return str(resolved) if resolved is not None else match.group(0)

            return re.sub(r"__([a-zA-Z0-9_]+)__", replace, value)

        elif isinstance(value, dict):
            return {
                substitute(k): substitute(v)
                for k, v in value.items()
            }

        elif isinstance(value, list):
            return [substitute(v) for v in value]

        else:
            return value

    return substitute(template)

def write_output(path, compiled_path, obj, name):
    if str(path).endswith(".yml") or str(path).endswith(".yaml"):
        out_file = compiled_path / f"{name}.yml"
    elif str(path).endswith(".json"):
        out_file = compiled_path / f"{name}.tf.json"
    else:
        raise ValueError(f"Unsupported template file type: {path}")
    
    path = out_file
 
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    with open(path, "w") as f:
        if str(path).endswith(".tf.json"):  # Updated extension
            json.dump(obj, f, indent=2)
        elif str(path).endswith(".yaml") or str(path).endswith(".yml"):
            yaml.safe_dump(obj, f)
        else:
            raise ValueError(f"Unsupported output type: {path}")
        print(f"[+] Wrote: {path}")

def write_helm_chart_output(chart_path, rendered_values_file, name, data, templates_dir, compiled_path, parameters):
    """
    Process Helm chart and values file.
    """

    # Write rendered values to a temp file
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".yml") as tf:
        yaml.dump(rendered_values_file, tf)
        tf.flush()
        rendered_values_path = tf.name

    try:
        # Build the output directory path
        #output_dir = compiled_path / name
        #os.makedirs(output_dir, exist_ok=True)
        output_dir = compiled_path

        # Run the Helm template command
        cmd = [
            "helm", "template", name,
            str(chart_path),
            "--namespace", parameters.get("namespace", "default"),
            "--output-dir", str(output_dir),
            "-f", rendered_values_path
        ]
        subprocess.run(cmd, check=True)
        print(f"[+] Rendered Helm chart for '{name}' to {output_dir}")

    finally:
        os.remove(rendered_values_path)
