import requests
from requests_toolbelt import MultipartEncoder

if __name__ == '__main__':
    url = "http://sp.int3.sonata-nfv.eu:5050/validate/package"
    file = open('../../../../../eu.sonata-nfv.eu.p-complex.0.1.son', 'rb')
    data = {'source': "embedded",
            'syntax': 'true',
            'integrity': 'true',
            'topology': 'true',
            'file': (file.name, file, 'application/octet-stream')
            }

    m = MultipartEncoder(data)
    headers = {'Content-Type': m.content_type}
    response = requests.post(url, headers=headers, data=m)
    print(response)
