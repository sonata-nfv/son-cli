export class Link {
  constructor(label, srcId, srcX, srcY, srcMinX, srcMinY,
    tgtId, tgtX, tgtY, tgtMinX, tgtMinY) {
    this.label = label;
    this.source = {
      id: srcId,
      x: srcX,
      y: srcY,
      mx: srcMinX,
      my: srcMinY,
    };
    this.target = {
      id: tgtId,
      x: tgtX,
      y: tgtY,
      mx: tgtMinX,
      my: tgtMinY,
    };
    this.graphsourceid = this.source.id;
    this.graphtargetid = this.target.id;
  }

  get id() {
    return `${this.source.id}${this.target.id}`;
  }

  get graphid() {
    return `${this.graphsourceid}${this.graphtargetid}`;
  }

  get reverseId() {
    return `${this.target.id}${this.source.id}`;
  }

  isEqual(linkB) {
    return this.id === linkB.id;
  }

  isInverse(linkB) {
    return this.reverseId === linkB.id;
  }

  isParallel(pathB) {
    return this.source.id === pathB.target.id
      && this.source.x === pathB.target.x
      && this.source.y === pathB.target.y
      && this.source.minx === pathB.target.minx
      && this.source.miny === pathB.target.miny
      && this.target.id === pathB.source.id
      && this.target.x === pathB.source.x
      && this.target.y === pathB.source.y
      && this.target.minx === pathB.source.minx
      && this.target.miny === pathB.source.miny;
  }

  setSourceCoords(x, y, mx, my) {
    this.source.x = x;
    this.source.y = y;
    this.source.mx = mx;
    this.source.my = my;
  }

  setTargetCoords(x, y, mx, my) {
    this.target.x = x;
    this.target.y = y;
    this.target.mx = mx;
    this.target.my = my;
  }

  get points() {
    return `${this.source.mx},${this.source.my} 
                ${(this.source.mx + this.target.mx) / 2}, 
                ${(this.source.my + this.target.my) / 2} 
                ${this.target.mx},${this.target.my}`;
  }
}

export default Link;
