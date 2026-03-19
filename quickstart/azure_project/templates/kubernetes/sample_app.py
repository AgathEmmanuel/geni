from geni.template import Template, KubernetesManifest, GeneratedFile, RenderContext


class SampleApp(Template):
    """Kubernetes manifests: Namespace, ConfigMap, ServiceAccount, Deployment, Service."""

    def render(self, context: RenderContext) -> list[GeneratedFile]:
        p = context.params
        app_name = p["app_name"]
        app_namespace = p["app_namespace"]
        app_image = p["app_image"]
        app_port = p.get("app_port", 80)
        app_replicas = p.get("app_replicas", 2)
        db_name = p.get("db_name", "appdb")
        storage_account_name = p.get("storage_account_name", "")

        labels = {
            "app.kubernetes.io/name": app_name,
            "app.kubernetes.io/managed-by": "geni",
        }

        workload_identity_label = {
            "azure.workload.identity/use": "true",
        }

        # -- Namespace -------------------------------------------------------
        namespace = {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": app_namespace,
                "labels": {
                    "app.kubernetes.io/name": app_namespace,
                },
            },
        }

        # -- ConfigMap -------------------------------------------------------
        configmap = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": f"{app_name}-config",
                "namespace": app_namespace,
                "labels": labels,
            },
            "data": {
                "DB_HOST": f"psql-myazureproject-dev.postgres.database.azure.com",
                "DB_PORT": "5432",
                "DB_NAME": db_name,
                "STORAGE_ACCOUNT": storage_account_name,
                "AZURE_STORAGE_CONTAINER": "app-data",
            },
        }

        # -- ServiceAccount --------------------------------------------------
        service_account = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {
                "name": f"{app_namespace}-sa",
                "namespace": app_namespace,
                "annotations": {
                    "azure.workload.identity/client-id": "<APP_WORKLOAD_IDENTITY_CLIENT_ID>",
                },
                "labels": labels,
            },
        }

        # -- Deployment ------------------------------------------------------
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": app_name,
                "namespace": app_namespace,
                "labels": labels,
            },
            "spec": {
                "replicas": app_replicas,
                "selector": {
                    "matchLabels": {
                        "app.kubernetes.io/name": app_name,
                    },
                },
                "template": {
                    "metadata": {
                        "labels": {
                            **labels,
                            **workload_identity_label,
                        },
                    },
                    "spec": {
                        "serviceAccountName": f"{app_namespace}-sa",
                        "containers": [
                            {
                                "name": app_name,
                                "image": app_image,
                                "ports": [
                                    {
                                        "containerPort": app_port,
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
                                        "port": app_port,
                                    },
                                    "initialDelaySeconds": 10,
                                    "periodSeconds": 30,
                                },
                                "readinessProbe": {
                                    "httpGet": {
                                        "path": "/",
                                        "port": app_port,
                                    },
                                    "initialDelaySeconds": 5,
                                    "periodSeconds": 10,
                                },
                            }
                        ],
                    },
                },
            },
        }

        # -- Service ---------------------------------------------------------
        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": app_name,
                "namespace": app_namespace,
                "labels": labels,
            },
            "spec": {
                "type": "ClusterIP",
                "ports": [
                    {
                        "port": 80,
                        "targetPort": app_port,
                        "protocol": "TCP",
                        "name": "http",
                    }
                ],
                "selector": {
                    "app.kubernetes.io/name": app_name,
                },
            },
        }

        manifests = [namespace, configmap, service_account, deployment, service]

        return [KubernetesManifest("sample-app.yml", manifests)]
