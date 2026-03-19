import os
import argparse
import re
import json
import yaml
import copy
import subprocess  # Add at the top with other imports
import importlib.util
from pathlib import Path
import shutil
from utils.base import load_template, render_template, write_output, resolve, write_hcl2json, write_helm_chart_output


"""
=== Example target file ===
data:
  project: project_name
compiled: compiled/terraform/project_name
resources:
  backend:
    template: terraform/backend.tf.json
    parameter:
      bucket_name: bucket_name
      tfstate_prefix: project_name
 
  provider:
    template: terraform/provider.tf.json
    parameter:
      project_name: data.project
===

=== File Structure ===

- compiled  
  |
  - terraform
    |
    - example1.tf.json
    - example2.tf.json
  - kubernetes
    |
    - example1.yml
    - example2.yml
- components  
  |
  - batch_buckets.py
- geni.py  
- targets  
  |
  - target1.yml
  - target2.yml
- templates  
  |
  - kubernetes  
    |
    - template1.yml
    - template2.yml
  - terraform
    - template1.tf.json
    - template2.tf.json
- utils
  |
  - base.py  
  - configure.py

"""

def clean_target_compiled(compiled_path):
    compiled_path = Path(compiled_path)
    if not compiled_path.exists():
        compiled_path.mkdir(parents=True, exist_ok=True)
        return

    for item in compiled_path.iterdir():
        if item.name.startswith(".terraform"):
            continue  # preserve .terraform files or directories
        if item.is_file():
            item.unlink()
            #print(f"[~] Deleted file: {item}")
        elif item.is_dir():
            # Recursively delete contents unless it's .terraform
            clean_target_compiled(item)
            try:
                item.rmdir()
                #print(f"[~] Deleted empty folder: {item}")
            except OSError:
                pass  # Folder not empty (maybe has .terraform inside), so skip

def clean_orphaned_compiled_dirs(compiled_roots, targets_dir):
    targets_dir = Path(targets_dir)
    valid_targets = {target.stem for target in targets_dir.glob("*.yml")}

    for root in compiled_roots:
        root = Path(root)
        if not root.exists():
            continue

        for subdir in root.iterdir():
            if subdir.is_dir() and subdir.name not in valid_targets:
                print(f"[~] Cleaning orphaned compiled dir: {subdir}")
                for item in subdir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                try:
                    subdir.rmdir()
                    print(f"[~] Removed orphaned compiled dir: {subdir}")
                except OSError:
                    print(f"[!] Could not remove {subdir}, non-empty (likely .terraform)")

def run_component(component_path, parameters, name, data, templates_dir, compiled_path):
    spec = importlib.util.spec_from_file_location("component", component_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Component should return a list of dicts with `filename`, `content`
    return module.generate(parameters, name, data, templates_dir, compiled_path)

def compile_target(target_file):
    with open(target_file) as f:
        config = yaml.safe_load(f)

    data = config.get("data", {})
    compiled_path = Path(config.get("compiled", f"compiled/{target_file.stem}"))
    clean_target_compiled(compiled_path)

    templates_dir = Path("templates")
    resources = config.get("resources", {})

    for name, resource in resources.items():

        if "template" in resource:
            template_path = templates_dir / resource["template"]

            template_path = write_hcl2json(template_path) or template_path

            template = load_template(template_path)

            """
            rendered = render_template(template, resource.get("parameter", {}), data)
            #print(rendered)
            write_output(template_path, compiled_path, rendered, name)

            """
            with open(template_path) as f:
                content=f.read()
                if "---" in content:
                    rendered_docs = [
                        render_template(doc, resource.get("parameter", {}), data)
                        for doc in template
                        if doc is not None
                    ]

                    output_file = compiled_path / f"{name}.yml"

                    os.makedirs(output_file.parent, exist_ok=True)

                    with open(output_file, "w") as f:
                        yaml.dump_all(rendered_docs, f, explicit_start=True)
                        print(f"[+] Wrote: {output_file}")
            
                else:

                    rendered = render_template(template, resource.get("parameter", {}), data)
                    #print(rendered)
                    write_output(template_path, compiled_path, rendered, name)

        elif "component" in resource:
            component_path = Path(resource["component"])
            run_component(component_path, resource.get("parameter", {}), name, data, templates_dir, compiled_path)

        elif "chart" in resource and "value" in resource:
            # Process Helm resource
            chart_path = templates_dir / resource["chart"]
            values_file_path = templates_dir / resource["value"]
            values_file = load_template(values_file_path)
            rendered_value_file = render_template(values_file, resource.get("parameter", {}), data)
            write_helm_chart_output(chart_path, rendered_value_file, name, data, templates_dir, compiled_path, resource.get("parameter", {}))

        else:
            print(f"[!] Skipping {name}, neither 'template' nor 'component' found.")

def compile_all_targets():
    for target_file in Path("targets").glob("*.yml"):
        compile_target(target_file)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--target", help="Name of the target to compile")
    args = parser.parse_args()
    #templates_dir = Path("templates")
    targets_dir = Path("targets")
    
    compiled_roots = [
        Path("compiled/terraform"),
        Path("compiled/kubernetes")
    ]

    if args.target:
        target_file = Path("targets") / f"{args.target}.yml"
        if not target_file.exists():
            print(f"[!] Target file not found: {target_file}")
            return
        compile_target(target_file)
    else:
        compile_all_targets()


        # After compilation, cleanup orphaned compiled dirs
        clean_orphaned_compiled_dirs(compiled_roots, targets_dir)

if __name__ == "__main__":
    main()
