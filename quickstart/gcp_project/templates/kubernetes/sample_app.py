from geni.template import Template, KubernetesManifest, GeneratedFile, RenderContext


class SampleAppTemplate(Template):
    """Generates Kubernetes manifests for a sample application including
    Namespace, ConfigMap, Deployment, Service, and ServiceAccount with
    Workload Identity annotation."""

    def render(self, context: RenderContext) -> list[GeneratedFile]:
        params = context.params
        app_name = params["app_name"]
        namespace = params["app_namespace"]
        image = params["app_image"]
        port = params["app_port"]
        env = params["environment"]
        project = params["project"]
        db_name = params["db_name"]
        db_instance_name = params["db_instance_name"]

        sa_name = f"{app_name}-workload"

        namespace_manifest = {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": namespace,
                "labels": {
                    "app.kubernetes.io/name": app_name,
                    "app.kubernetes.io/part-of": app_name,
                    "environment": env,
                },
            },
        }

        configmap_manifest = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": f"{app_name}-config",
                "namespace": namespace,
                "labels": {
                    "app.kubernetes.io/name": app_name,
                    "app.kubernetes.io/component": "config",
                },
            },
            "data": {
                "DB_HOST": "127.0.0.1",
                "DB_PORT": "5432",
                "DB_NAME": db_name,
                "DB_INSTANCE": f"{project}:us-central1:{db_instance_name}",
                "BUCKET_ASSETS": f"{project}-{env}-app-assets",
                "BUCKET_UPLOADS": f"{project}-{env}-app-uploads",
                "ENVIRONMENT": env,
            },
        }

        service_account_manifest = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {
                "name": app_name,
                "namespace": namespace,
                "labels": {
                    "app.kubernetes.io/name": app_name,
                    "app.kubernetes.io/component": "serviceaccount",
                },
                "annotations": {
                    "iam.gke.io/gcp-service-account": f"{sa_name}@{project}.iam.gserviceaccount.com",
                },
            },
        }

        deployment_manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": app_name,
                "namespace": namespace,
                "labels": {
                    "app.kubernetes.io/name": app_name,
                    "app.kubernetes.io/component": "server",
                    "environment": env,
                },
            },
            "spec": {
                "replicas": 2,
                "selector": {
                    "matchLabels": {
                        "app.kubernetes.io/name": app_name,
                    }
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app.kubernetes.io/name": app_name,
                            "app.kubernetes.io/component": "server",
                            "environment": env,
                        },
                    },
                    "spec": {
                        "serviceAccountName": app_name,
                        "containers": [
                            {
                                "name": app_name,
                                "image": image,
                                "ports": [
                                    {
                                        "name": "http",
                                        "containerPort": port,
                                        "protocol": "TCP",
                                    }
                                ],
                                "envFrom": [
                                    {
                                        "configMapRef": {
                                            "name": f"{app_name}-config",
                                        }
                                    }
                                ],
                                "resources": {
                                    "requests": {
                                        "cpu": "250m",
                                        "memory": "256Mi",
                                    },
                                    "limits": {
                                        "cpu": "500m",
                                        "memory": "512Mi",
                                    },
                                },
                                "livenessProbe": {
                                    "httpGet": {
                                        "path": "/",
                                        "port": "http",
                                    },
                                    "initialDelaySeconds": 10,
                                    "periodSeconds": 10,
                                },
                                "readinessProbe": {
                                    "httpGet": {
                                        "path": "/",
                                        "port": "http",
                                    },
                                    "initialDelaySeconds": 5,
                                    "periodSeconds": 5,
                                },
                            }
                        ],
                    },
                },
            },
        }

        service_manifest = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": app_name,
                "namespace": namespace,
                "labels": {
                    "app.kubernetes.io/name": app_name,
                    "app.kubernetes.io/component": "service",
                },
            },
            "spec": {
                "type": "ClusterIP",
                "ports": [
                    {
                        "name": "http",
                        "port": 80,
                        "targetPort": "http",
                        "protocol": "TCP",
                    }
                ],
                "selector": {
                    "app.kubernetes.io/name": app_name,
                },
            },
        }

        return [
            KubernetesManifest(name="00-namespace", content=namespace_manifest),
            KubernetesManifest(name="01-configmap", content=configmap_manifest),
            KubernetesManifest(name="02-serviceaccount", content=service_account_manifest),
            KubernetesManifest(name="03-deployment", content=deployment_manifest),
            KubernetesManifest(name="04-service", content=service_manifest),
        ]
