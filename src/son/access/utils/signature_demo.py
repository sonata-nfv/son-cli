
def signature():
    from son.access.access import AccessClient
    from son.workspace.workspace import Workspace
    from Crypto.PublicKey import RSA
    from Crypto.Hash import SHA256

    ws = Workspace('~/workspace/ws1')
    ac = AccessClient(ws)
    key = RSA.generate(2048)

    # package_path = 'son/access/samples/sonata-demo.son'
    package_path = '../samples/sonata-demo.son'
    with open(package_path, 'rb') as fhandle:
        package_content = fhandle.read()

    package_hash = SHA256.new(package_content).digest()
    signature = ac.sign_package(package_path,
                                private_key=key.exportKey().decode('utf-8'))
    public_key = key.publickey()
    print(public_key.verify(package_hash, (int(signature),)))
