export class Node {
  constructor(id, label, level, type, parentid) {
    this.id = id;
    this.label = label;
    this.level = level;
    this.parentid = parentid;
    this.children = [];
    this.connections = [];
    this.type = type;
  }

  getType() {
    if (this.type === 'bridge') return null;
    switch (this.level) {
      case 0:
        return 'ns';
      case 1:
        return 'vnf';
      case 2:
        return 'vdu';
      default:
        return null;
    }
  }

  compare(other) {
    if (!(other instanceof Node)) return false;

    return this.parentid === other.parentid && this.id === other.id;
  }
}

export default Node;
