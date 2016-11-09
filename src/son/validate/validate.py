import yaml

class UndirectedGraph(object):

    def __init__(self):
        pass


class Validator(object):


    def __init__(self, project):
        self._project = project

    def validate(self):
        self._build_service_graph()

    def _build_service_graph(self):

        # load project service descriptor
        nsd_file = self._project.get_ns_descriptor()
        with open(nsd_file) as _file:
            nsd = yaml.load(_file)
            assert nsd is not None

        # load all project function descriptors
        prj_vnfds = {}
        vnfd_files = self._project.get_vnf_descriptors()
        for vnfd_file in vnfd_files:
            with open(vnfd_file) as _file:
                vnfd = yaml.load(_file)
                assert vnfd is not None
                vnf_combo_id = vnfd['vendor'] + '.' + vnfd['name'] + '.' + \
                               vnfd['version']
                prj_vnfds[vnf_combo_id] = vnfd

        # assign vnf descriptors referenced in the service descriptor
        ref_vnfds = {}
        for func in nsd['network_functions']:
            vnf_combo_id = func['vnd_vendor'] + '.' + func['vnf_name'] + \
                           '.' + func['vnf_version']
            if vnf_combo_id in prj_vnfds.keys():
                ref_vnfds[func['vnf_id']] = prj_vnfds[vnf_combo_id]




