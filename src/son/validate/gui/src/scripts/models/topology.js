import { Node } from './node';

export class Topology {
  constructor(ifaces, links, noBridges) {
    this.root = new Node('root', 'root', -1, 'root');
    this.build(ifaces, links, noBridges);
  }

  build(ifaces, links, noBridges) {
    let filteredIfaces = ifaces;
    let filteredLinks = links;
    if (noBridges) {
      const tmp = Topology.removeBridges(ifaces, links);
      filteredIfaces = tmp.ifaces;
      filteredLinks = tmp.links;
    }
    this.buildTree(Topology.buildNodes(filteredIfaces));
    this.links = Topology.buildLinks(filteredLinks, ifaces);
  }

  static removeBridges(ifaces, links) {
    return {
      ifaces: ifaces.filter(iface => iface.type !== 'bridge' && iface.type !== 'br-iface'),
      links: links.filter(link => link.type !== 'br-iface' && link.label !== 'mgmt'),
    };
  }

  static buildLinks(links, ifaces) {
    const tmpMgmt = links.filter(link => link.label === 'mgmt');
    const tmpSorted = links.filter(link => link.label !== 'mgmt');

    tmpSorted.forEach((link) => {
      const foundSource = ifaces.find(iface => iface.id === link.source);
      const foundTarget = ifaces.find(iface => iface.id === link.target);
      if (foundSource && foundTarget) {
        link.slevel = Number(foundSource.level);
        link.tlevel = Number(foundTarget.level);
      }
    });

    // tmpSorted.sort((a, b) => a.level - b.level);
    tmpSorted.sort((a, b) => {
      const res = (a.slevel + a.tlevel) - (b.slevel + b.tlevel);
      if (res === 0) {
        return a.slevel < b.slevel;
      }
      return res;
    });

    return [...tmpSorted, ...tmpMgmt];
  }

  static buildNodes(ifaces) {
    const nodes = [];

    ifaces.forEach((iface) => {
      if (iface.parent_id === '') {
        iface.parent_id = 'root';
      } else if (iface.type === 'bridge') {
        iface.node_id = iface.id;
        iface.node_label = iface.label;
      }

      const exists = nodes.find(node => node.id === iface.node_id
        && iface.parent_id === node.parentid);
      if (!exists) {
        const newNode = new Node(iface.node_id, iface.node_label,
          Number(iface.level), iface.type === 'bridge' ? 'bridge' : 'sum', iface.parent_id);
        newNode.connections.push({
          id: iface.id,
          label: iface.label,
        });
        nodes.push(newNode);
      } else {
        exists.connections.push({
          id: iface.id,
          label: iface.label,
        });
      }
    });

    return nodes;
  }

  buildTree(nodes) {
    let i = 0;
    while (nodes.length) {
      const found = this.searchTree(this.root, nodes[i].parentid);

      if (found) {
        found.children.push(nodes[i]);
        nodes.splice(i, 1);
        i = 0;
      } else if (i === nodes.length) {
        i = 0;
      } else {
        i += 1;
      }
    }
  }

  searchTree(root, id) {
    return this.recSearch(root, id);
  }

  recSearch(datum, id) {
    if (datum.id === id) return datum;
    if (datum.children && datum.children.length) {
      let res = null;
      for (let i = 0; res == null && i < datum.children.length; i += 1) {
        res = this.recSearch(datum.children[i], id);
      }

      return res;
    }

    return null;
  }

}

export default Topology;
