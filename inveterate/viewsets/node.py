from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from requests.exceptions import ConnectionError, Timeout
from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException

from .base import DynamicPageModelViewSet
from .. import models
from .. import serializers


class NodeViewSet(DynamicPageModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = models.Node.objects.order_by('pk')
    serializer_class = serializers.NodeSerializer

    @action(methods=['get'], detail=False, description="the stats")
    def stats(self, request, pk=None):
        stats = {
            'cluster': {
                'type': 'count',
                'label': 'Clusters',
                'value': models.Cluster.objects.all().count()
            },
            'node': {
                'type': 'count',
                'label': 'Nodes',
                'value': models.Node.objects.all().count()
            },
            'service': {
                'type': 'count',
                'label': 'Services',
                'value': models.Service.objects.all().exclude(status='destroyed').count()
            }
        }
        return Response(stats, status=202)

    @action(methods=['get'], detail=True)
    def status(self, request, pk=None):
        """Get Proxmox node status and resource usage"""
        try:
            node = models.Node.objects.get(pk=pk)

            if not node.cluster:
                return Response({
                    'success': False,
                    'message': 'Node has no associated cluster'
                }, status=status.HTTP_400_BAD_REQUEST)

            cluster = node.cluster
            proxmox = ProxmoxAPI(cluster.host, user=cluster.user, token_name='inveterate',
                                 token_value=cluster.key,
                                 verify_ssl=False, port=8006, timeout=10)

            # Get node status and resource information
            node_status = proxmox.nodes(node.name).status.get()

            # Calculate resource usage percentages
            cpu_usage = node_status.get('cpu', 0)
            memory_used = node_status.get('memory', {}).get('used', 0)
            memory_total = node_status.get('memory', {}).get('total', 1)
            memory_usage = memory_used / memory_total if memory_total > 0 else 0

            # Get storage information
            storage_info = []
            try:
                storages = proxmox.nodes(node.name).storage.get()
                for storage in storages:
                    if storage.get('enabled', 0) == 1:
                        storage_info.append({
                            'storage': storage.get('storage'),
                            'type': storage.get('type'),
                            'used': storage.get('used', 0),
                            'total': storage.get('total', 0),
                            'usage': storage.get('used', 0) / storage.get('total', 1) if storage.get('total', 0) > 0 else 0
                        })
            except Exception:
                storage_info = []

            # Get uptime
            uptime_seconds = node_status.get('uptime', 0)
            uptime_days = uptime_seconds // 86400
            uptime_hours = (uptime_seconds % 86400) // 3600
            uptime_minutes = (uptime_seconds % 3600) // 60

            if uptime_days > 0:
                uptime_str = f"{uptime_days}d {uptime_hours}h {uptime_minutes}m"
            elif uptime_hours > 0:
                uptime_str = f"{uptime_hours}h {uptime_minutes}m"
            else:
                uptime_str = f"{uptime_minutes}m"

            return Response({
                'success': True,
                'online': True,
                'cpu': cpu_usage,
                'memory': {
                    'used': memory_used,
                    'total': memory_total,
                    'usage': memory_usage
                },
                'storage': storage_info,
                'uptime': uptime_str,
                'uptime_seconds': uptime_seconds,
                'pve_version': node_status.get('pveversion', 'Unknown'),
                'kernel_version': node_status.get('kversion', 'Unknown'),
                'load_average': node_status.get('loadavg', []),
                'node_info': {
                    'cpu_info': node_status.get('cpuinfo', {}),
                    'memory_total_gb': round(memory_total / (1024**3), 2),
                    'memory_used_gb': round(memory_used / (1024**3), 2)
                }
            }, status=status.HTTP_200_OK)

        except models.Node.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Node not found'
            }, status=status.HTTP_404_NOT_FOUND)

        except (ConnectionError, Timeout):
            return Response({
                'success': False,
                'online': False,
                'message': 'Connection failed: Unable to reach Proxmox node'
            }, status=status.HTTP_200_OK)  # Return 200 with offline status

        except ResourceException:
            return Response({
                'success': False,
                'online': False,
                'message': 'Authentication failed: Check cluster credentials'
            }, status=status.HTTP_200_OK)  # Return 200 with offline status

        except Exception as e:
            return Response({
                'success': False,
                'online': False,
                'message': f'Status check failed: {str(e)}'
            }, status=status.HTTP_200_OK)  # Return 200 with offline status

    @action(methods=['post'], detail=False)
    def bulk_import(self, request):
        """Import multiple nodes from Proxmox clusters"""
        nodes_data = request.data.get('nodes', [])

        if not nodes_data:
            return Response({
                'success': False,
                'message': 'No nodes provided for import'
            }, status=status.HTTP_400_BAD_REQUEST)

        imported_nodes = []
        errors = []

        for node_data in nodes_data:
            try:
                cluster_id = node_data.get('cluster_id')
                node_name = node_data.get('name')
                node_status = node_data.get('status')
                node_mem = node_data.get('mem')
                node_maxmem = node_data.get('maxmem')
                node_cpu = node_data.get('cpu')
                node_maxcpu = node_data.get('maxcpu')
                node_disk = node_data.get('disk')
                node_maxdisk = node_data.get('maxdisk')

                if not cluster_id or not node_name:
                    errors.append(f"Missing cluster_id or name for node: {node_data}")
                    continue

                try:
                    cluster = models.Cluster.objects.get(pk=cluster_id)
                except models.Cluster.DoesNotExist:
                    errors.append(f"Cluster {cluster_id} not found for node {node_name}")
                    continue

                # Check if node already exists
                if models.Node.objects.filter(name=node_name, cluster=cluster).exists():
                    errors.append(f"Node {node_name} already exists in cluster {cluster.name}")
                    continue

                # Create the node with resource information
                node = models.Node.objects.create(
                    name=node_name,
                    cluster=cluster,
                    # Convert bytes to GB for storage, MB for RAM
                    size=int(node_maxdisk / (1024**3)) if node_maxdisk else 0,
                    ram=int(node_maxmem / (1024**2)) if node_maxmem else 0,
                    cores=int(node_maxcpu) if node_maxcpu else 0
                )

                imported_nodes.append({
                    'id': node.id,
                    'name': node.name,
                    'cluster': cluster.name
                })

            except Exception as e:
                errors.append(f"Error importing node {node_data.get('name', 'unknown')}: {str(e)}")

        return Response({
            'success': len(imported_nodes) > 0,
            'imported_count': len(imported_nodes),
            'error_count': len(errors),
            'imported_nodes': imported_nodes,
            'errors': errors
        }, status=status.HTTP_201_CREATED if imported_nodes else status.HTTP_400_BAD_REQUEST)

    @action(methods=['get'], detail=True)
    def vms(self, request, pk=None):
        """Get VMs/LXCs running on this node"""
        try:
            node = models.Node.objects.get(pk=pk)

            if not node.cluster:
                return Response({
                    'success': False,
                    'message': 'Node has no associated cluster'
                }, status=status.HTTP_400_BAD_REQUEST)

            cluster = node.cluster
            proxmox = ProxmoxAPI(cluster.host, user=cluster.user, token_name='inveterate',
                                 token_value=cluster.key,
                                 verify_ssl=False, port=8006, timeout=10)

            # Get VMs and LXCs from this specific node
            try:
                qemu_vms = proxmox.nodes(node.name).qemu.get()
            except Exception:
                qemu_vms = []

            try:
                lxc_containers = proxmox.nodes(node.name).lxc.get()
            except Exception:
                lxc_containers = []

            # Format the VM data
            vms = []

            # Process QEMU VMs
            for vm in qemu_vms:
                vms.append({
                    'vmid': vm.get('vmid'),
                    'name': vm.get('name', f"vm-{vm.get('vmid')}"),
                    'type': 'qemu',
                    'status': vm.get('status', 'unknown'),
                    'mem': vm.get('mem', 0),
                    'maxmem': vm.get('maxmem', 0),
                    'cpus': vm.get('cpus', 1),
                    'disk': vm.get('disk', 0),
                    'maxdisk': vm.get('maxdisk', 0),
                    'node_id': node.id,
                    'node_name': node.name,
                    'uptime': vm.get('uptime', 0)
                })

            # Process LXC containers
            for container in lxc_containers:
                vms.append({
                    'vmid': container.get('vmid'),
                    'name': container.get('name', f"ct-{container.get('vmid')}"),
                    'type': 'lxc',
                    'status': container.get('status', 'unknown'),
                    'mem': container.get('mem', 0),
                    'maxmem': container.get('maxmem', 0),
                    'cpus': container.get('cpus', 1),
                    'disk': container.get('disk', 0),
                    'maxdisk': container.get('maxdisk', 0),
                    'node_id': node.id,
                    'node_name': node.name,
                    'uptime': container.get('uptime', 0)
                })

            return Response({
                'success': True,
                'node': {
                    'id': node.id,
                    'name': node.name,
                    'cluster': cluster.name
                },
                'vms': vms,
                'vm_count': len(vms)
            }, status=status.HTTP_200_OK)

        except models.Node.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Node not found'
            }, status=status.HTTP_404_NOT_FOUND)

        except (ConnectionError, Timeout):
            return Response({
                'success': False,
                'message': 'Connection failed: Unable to reach Proxmox node'
            }, status=status.HTTP_400_BAD_REQUEST)

        except ResourceException:
            return Response({
                'success': False,
                'message': 'Authentication failed: Check cluster credentials'
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Failed to get VMs: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)


class NodeDiskViewSet(DynamicPageModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = models.NodeDisk.objects.order_by('pk')
    serializer_class = serializers.NodeDiskSerializer

    @action(methods=['get'], detail=False)
    def discover_all(self, request):
        """Discover storage disks from all nodes"""
        try:
            all_nodes = models.Node.objects.filter(cluster__isnull=False)

            if not all_nodes.exists():
                return Response({
                    'success': False,
                    'message': 'No nodes with clusters found'
                }, status=status.HTTP_400_BAD_REQUEST)

            discovered_disks = []
            node_errors = []

            for node in all_nodes:
                try:
                    cluster = node.cluster
                    proxmox = ProxmoxAPI(cluster.host, user=cluster.user, token_name='inveterate',
                                         token_value=cluster.key,
                                         verify_ssl=False, port=8006, timeout=10)

                    # Get storage information for this node
                    try:
                        storages = proxmox.nodes(node.name).storage.get()

                        for storage in storages:
                            if storage.get('enabled', 0) == 1:  # Only enabled storage
                                # Get detailed storage info
                                try:
                                    storage_detail = proxmox.nodes(node.name).storage(storage['storage']).status.get()
                                except Exception:
                                    storage_detail = {}

                                disk_info = {
                                    'node_id': node.id,
                                    'node_name': node.name,
                                    'cluster_name': cluster.name,
                                    'storage_name': storage.get('storage'),
                                    'storage_type': storage.get('type'),
                                    'content': storage.get('content', ''),
                                    'shared': storage.get('shared', 0) == 1,
                                    'enabled': storage.get('enabled', 0) == 1,
                                    'total': storage_detail.get('total', 0),
                                    'used': storage_detail.get('used', 0),
                                    'available': storage_detail.get('avail', 0),
                                    'usage_percent': round((storage_detail.get('used', 0) / storage_detail.get('total', 1)) * 100, 2) if storage_detail.get('total', 0) > 0 else 0
                                }

                                discovered_disks.append(disk_info)

                    except Exception as storage_error:
                        node_errors.append(f"Failed to get storage from {node.name}: {str(storage_error)}")

                except (ConnectionError, Timeout):
                    node_errors.append(f"Connection failed to {node.name}")
                except ResourceException:
                    node_errors.append(f"Authentication failed for {node.name}")
                except Exception as e:
                    node_errors.append(f"Error with {node.name}: {str(e)}")

            # Group shared disks
            shared_disks = {}
            unique_disks = []

            for disk in discovered_disks:
                if disk['shared']:
                    storage_key = f"{disk['storage_name']}_{disk['storage_type']}"
                    if storage_key not in shared_disks:
                        shared_disks[storage_key] = {
                            'disk_info': disk,
                            'nodes': [{'id': disk['node_id'], 'name': disk['node_name']}]
                        }
                    else:
                        shared_disks[storage_key]['nodes'].append({'id': disk['node_id'], 'name': disk['node_name']})
                else:
                    unique_disks.append(disk)

            # Convert shared disks back to list format
            for shared_group in shared_disks.values():
                disk_info = shared_group['disk_info']
                disk_info['shared_nodes'] = shared_group['nodes']
                unique_disks.append(disk_info)

            return Response({
                'success': True,
                'discovered_disks': unique_disks,
                'total_disks': len(unique_disks),
                'node_errors': node_errors,
                'error_count': len(node_errors)
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Failed to discover disks: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['post'], detail=False)
    def bulk_import(self, request):
        """Import multiple storage disks"""
        disks_data = request.data.get('disks', [])

        if not disks_data:
            return Response({
                'success': False,
                'message': 'No disks provided for import'
            }, status=status.HTTP_400_BAD_REQUEST)

        imported_disks = []
        errors = []

        for disk_data in disks_data:
            try:
                storage_name = disk_data.get('storage_name')
                storage_type = disk_data.get('storage_type')
                total_size = disk_data.get('total', 0)
                shared = disk_data.get('shared', False)

                if not storage_name:
                    errors.append(f"Missing storage name for disk: {disk_data}")
                    continue

                # Convert bytes to GB
                size_gb = int(total_size / (1024**3)) if total_size else 0

                if shared and disk_data.get('shared_nodes'):
                    # Handle shared disk - assign to multiple nodes
                    for node_info in disk_data['shared_nodes']:
                        try:
                            node = models.Node.objects.get(pk=node_info['id'])

                            # Check if disk already exists for this node
                            if models.NodeDisk.objects.filter(name=storage_name, node=node).exists():
                                continue  # Skip if already exists

                            disk = models.NodeDisk.objects.create(
                                node=node,
                                name=f"{storage_name} ({storage_type})",
                                size=size_gb,
                                primary=storage_type in ['local', 'local-lvm', 'dir'],
                                shared=True
                            )

                            imported_disks.append({
                                'id': disk.id,
                                'name': disk.name,
                                'node': node.name,
                                'size_gb': size_gb,
                                'shared': True
                            })

                        except models.Node.DoesNotExist:
                            errors.append(f"Node {node_info['id']} not found for shared disk {storage_name}")
                else:
                    # Handle non-shared disk
                    node_id = disk_data.get('node_id')
                    if not node_id:
                        errors.append(f"Missing node_id for non-shared disk: {storage_name}")
                        continue

                    try:
                        node = models.Node.objects.get(pk=node_id)

                        # Check if disk already exists
                        if models.NodeDisk.objects.filter(name=storage_name, node=node).exists():
                            errors.append(f"Disk {storage_name} already exists on node {node.name}")
                            continue

                        disk = models.NodeDisk.objects.create(
                            node=node,
                            name=f"{storage_name} ({storage_type})",
                            size=size_gb,
                            primary=storage_type in ['local', 'local-lvm', 'dir']
                        )

                        imported_disks.append({
                            'id': disk.id,
                            'name': disk.name,
                            'node': node.name,
                            'size_gb': size_gb,
                            'shared': False
                        })

                    except models.Node.DoesNotExist:
                        errors.append(f"Node {node_id} not found for disk {storage_name}")

            except Exception as e:
                errors.append(f"Error importing disk {disk_data.get('storage_name', 'unknown')}: {str(e)}")

        return Response({
            'success': len(imported_disks) > 0,
            'imported_count': len(imported_disks),
            'error_count': len(errors),
            'imported_disks': imported_disks,
            'errors': errors
        }, status=status.HTTP_201_CREATED if imported_disks else status.HTTP_400_BAD_REQUEST)
