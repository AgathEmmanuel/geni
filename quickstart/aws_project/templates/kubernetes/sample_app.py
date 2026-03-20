from geni.template import Template, KubernetesManifest, GeneratedFile, RenderContext


class SampleAppTemplate(Template):
    """Generates Kubernetes manifests for a sample application including Namespace,
    ConfigMap, ServiceAccount (with IRSA annotation), Deployment, and Service."""

    def render(self, context: RenderContext) -> list[GeneratedFile]:
        params = context.params
        app_name = params["app_name"]
        namespace = params["app_namespace"]
        image = params["app_image"]
        port = params["app_port"]
        env = params["environment"]
        project = params["project"]
        db_name = params["db_name"]

        prefix = f"{project}-{env}"

        labels = {
            "app.kubernetes.io/name": app_name,
            "app.kubernetes.io/instance": f"{app_name}-{env}",
            "app.kubernetes.io/managed-by": "geni",
            "app.kubernetes.io/part-of": project,
            "environment": env,
        }

        # --- Namespace ---
        namespace_manifest = {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": namespace,
                "labels": {
                    "name": namespace,
                    "environment": env,
                },
            },
        }

        # --- ConfigMap ---
        configmap = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": f"{app_name}-config",
                "namespace": namespace,
                "labels": labels,
            },
            "data": {
                "DB_HOST": f"{prefix}-postgres.xxxxxxxxxxxx.{env}.rds.amazonaws.com",
                "DB_NAME": db_name,
                "DB_PORT": "5432",
                "BUCKET_ASSETS": f"{prefix}-app-assets",
                "BUCKET_UPLOADS": f"{prefix}-app-uploads",
                "ENVIRONMENT": env,
            },
        }

        # --- ServiceAccount (annotated for IRSA) ---
        service_account = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {
                "name": app_name,
                "namespace": namespace,
                "labels": labels,
                "annotations": {
                    "eks.amazonaws.com/role-arn": f"arn:aws:iam::ACCOUNT_ID:role/{prefix}-{app_name}-irsa-role",
                },
            },
        }

        # --- Deployment ---
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": app_name,
                "namespace": namespace,
                "labels": labels,
            },
            "spec": {
                "replicas": 2,
                "selector": {
                    "matchLabels": {
                        "app.kubernetes.io/name": app_name,
                        "app.kubernetes.io/instance": f"{app_name}-{env}",
                    },
                },
                "template": {
                    "metadata": {
                        "labels": labels,
                    },
                    "spec": {
                        "serviceAccountName": app_name,
                        "securityContext": {
                            "runAsNonRoot": True,
                            "runAsUser": 1000,
                            "fsGroup": 1000,
                        },
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
                                        "cpu": "100m",
                                        "memory": "128Mi",
                                    },
                                    "limits": {
                                        "cpu": "500m",
                                        "memory": "256Mi",
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

        # --- Service ---
        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": app_name,
                "namespace": namespace,
                "labels": labels,
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
                    "app.kubernetes.io/instance": f"{app_name}-{env}",
                },
            },
        }

        manifests = [
            namespace_manifest,
            configmap,
            service_account,
            deployment,
            service,
        ]

        return KubernetesManifest(filename="sample-app.yml", content=manifests)
