import yaml

# import sys; print('Python %s on %s' % (sys.version, sys.platform))
# sys.path.extend(['/home/osboxes/sonata/son-cli/src'])

# Create a config descriptor for workspace
conf_d = {
 'name': 'ws1',
 'log_level': 'info',
 'version': '0.03',
 'service_platforms': {
      'sp1': {'url': 'http://sp.int3.sonata-nfv.eu:32001',
              'credentials': {
                    'username': 'user01',
                    'password': '1234',
                    'token_file': 'token.txt'},
              'signature': {
                  'pub_key': 'pub_key.pem',
                  'prv_key': 'prv_key.pem',
                  'cert': None}}},
 'default_service_platform': 'sp1',
 'default_descriptor_extension': 'yml',
 'schemas_local_master': '~/.son-schema',
 'schemas_remote_master': 'https://raw.githubusercontent.com/'
                          'sonata-nfv/son-schema/master/',
 'platforms_dir': 'platforms',
 'catalogues_dir': 'catalogues',
 'configuration_dir': 'configuration',
 'projects_dir': 'projects',
 'validate_watch': '~/.son-workspace/projects'
}

conf_y = yaml.dump(conf_d)
with open('workspace.yml', "wb") as _file:
            _file.write(bytes(conf_y, 'UTF-8'))
