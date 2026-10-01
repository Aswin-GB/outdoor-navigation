"""
Django management command to benchmark routing performance.
"""
import time
import statistics
from django.core.management.base import BaseCommand
from routing_engine.manager import get_graph_manager
from routing_engine.service import RoutingService
from routing_engine.astar import astar


class Command(BaseCommand):
    help = 'Benchmark routing performance'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('=== Routing Benchmark ==='))

        # Benchmark graph load
        self.stdout.write('\n1. Graph Load Time:')
        start = time.perf_counter()
        gm = get_graph_manager()
        graph = gm.load_graph()
        load_time = (time.perf_counter() - start) * 1000
        self.stdout.write(f'   Load time: {load_time:.2f}ms')
        self.stdout.write(f'   Nodes: {len(graph.nodes)}')
        self.stdout.write(f'   Edges: {len(graph.edges)}')

        # Benchmark A* runs
        self.stdout.write('\n2. A* Performance:')
        nodes = list(graph.nodes.keys())
        if len(nodes) < 2:
            self.stdout.write(self.style.ERROR('   Not enough nodes for benchmark'))
            return

        latencies = []
        for i in range(min(20, len(nodes) - 1)):
            source = nodes[i]
            dest = nodes[i + 1]

            graph_dict = {
                'nodes': graph.nodes,
                'adjacency': graph.adjacency,
            }

            start = time.perf_counter()
            result = astar(graph_dict, source, dest)
            elapsed = (time.perf_counter() - start) * 1000

            if result:
                latencies.append(elapsed)

        if latencies:
            self.stdout.write(f'   Runs: {len(latencies)}')
            self.stdout.write(f'   Average: {statistics.mean(latencies):.2f}ms')
            self.stdout.write(f'   Median: {statistics.median(latencies):.2f}ms')
            self.stdout.write(f'   Min: {min(latencies):.2f}ms')
            self.stdout.write(f'   Max: {max(latencies):.2f}ms')
            self.stdout.write(f'   Std Dev: {statistics.stdev(latencies):.2f}ms' if len(latencies) > 1 else '   Std Dev: N/A')

        # Benchmark route service (skip if Redis unavailable)
        self.stdout.write('\n3. Route Service:')
        service = RoutingService()
        route_latencies = []

        # Check Redis availability first
        redis_available = service._is_redis_available()
        if not redis_available:
            self.stdout.write(self.style.WARNING('   Redis unavailable - skipping route service benchmark'))
            self.stdout.write('   (Route service requires Redis for caching)')
        else:
            for i in range(min(10, len(nodes) - 1)):
                source_node = graph.nodes[nodes[i]]
                dest_node = graph.nodes[nodes[i + 1]]

                start = time.perf_counter()
                result = service.compute_route(
                    source_node['lat'], source_node['lng'],
                    dest_node['lat'], dest_node['lng'],
                )
                elapsed = (time.perf_counter() - start) * 1000

                if result.get('success'):
                    route_latencies.append(elapsed)

            if route_latencies:
                self.stdout.write(f'   Successful routes: {len(route_latencies)}')
                self.stdout.write(f'   Average: {statistics.mean(route_latencies):.2f}ms')
                self.stdout.write(f'   Min: {min(route_latencies):.2f}ms')
                self.stdout.write(f'   Max: {max(route_latencies):.2f}ms')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Benchmark complete'))
