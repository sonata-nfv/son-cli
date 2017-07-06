import { LINK_SEL, NODE_SEL, FWPATH_SEL } from './viewer-conf';

const lineDivide = [3 / 4, 1 / 4];

export class LinkSelectionWrapper {
  constructor(base, datum) {
    this.isWarn = false;
    this.isError = false;
    this.isInverse = false;
    this.graphOnly = false;
    this.graphMode = false;
    this.pathIndexes = [];
    this.parallelOffset = {
      x: 0,
      y: 0,
    };
    this.group = base.insert('g', `g.${NODE_SEL.BASE}`)
      .classed(LINK_SEL.GROUP, true)
      .datum(datum);
    this.currCoords = {
      x1: this.datum.source.mx,
      y1: this.datum.source.my,
      x2: this.datum.target.mx,
      y2: this.datum.target.my,
    };
    this.selection = this.group.append('polyline')
      .classed(LINK_SEL.BASE, true)
      .attr('points', this.getPointsString())
      .on('mouseover', () => {
        this.selection.classed(LINK_SEL.HOVER, true);
        this.indexText.classed(FWPATH_SEL.INDEX_HOVERED, true);
        this.selection.style('stroke-width', 5);
      })
      .on('mouseout', () => {
        this.selection.classed(LINK_SEL.HOVER, false);
        this.indexText.classed(FWPATH_SEL.INDEX_HOVERED, false);
        this.selection.style('stroke-width', null);
      });
    this.indexText = this.group.insert('text', `g.${NODE_SEL.BASE}`)
      .classed(FWPATH_SEL.INDEX, true)
      .attr('x', d => (d.source.mx + d.target.mx) / 2)
      .attr('y', d => (d.source.my + d.target.my) / 2)
      .attr('text-anchor', 'middle');

    this.positionIndex();
  }

  get datum() {
    return this.group.datum();
  }

  isEqual(linkB) {
    return this.datum.isEqual(linkB);
  }

  isGraphEqual(linkB) {
    return this.datum.graphid === linkB.id;
  }

  isReverse(linkB) {
    return this.datum.isInverse(linkB);
  }

  setIndexesText(index) {
    this.pathIndexes.push(index);
    this.indexText.text(this.pathIndexes.join(', '));
  }

  clearIndexes() {
    this.pathIndexes.length = 0;
  }

  positionIndex() {
    const result = this.calcCircleIntersect();

    this.indexText
      .attr('x', result.px)
      .attr('y', result.py)
      .attr('text-anchor', 'middle');
  }

/**
 * Calculates the 2 points of interception between
 * the circle of radius equal to 2 / 3 of the link and the
 * circle around the path marker.
 */
  calcCircleIntersect() {
    const pos1 = this.isInverse ? 0 : 1;
    const pos2 = this.isInverse ? 1 : 0;
    let p0 = {
      x: this.isInverse ? this.currCoords.x2 : this.currCoords.x1,
      y: this.isInverse ? this.currCoords.y2 : this.currCoords.y1,
    };
    let p1 = {
      x: (lineDivide[pos1] * this.currCoords.x1) + (lineDivide[pos2] * this.currCoords.x2),
      y: (lineDivide[pos1] * this.currCoords.y1) + (lineDivide[pos2] * this.currCoords.y2),
    };
    if (p0.x === p1.x && p0.y === p1.y) {
      p1.x += 0.01;
      p1.y += 0.01;
    }
    const startRadius = Math.sqrt(((p1.x - p0.x) ** 2) + ((p1.y - p0.y) ** 2));
    const endRadius = 20;
    const r0 = this.isInverse ? endRadius : startRadius;
    const r1 = this.isInverse ? startRadius : endRadius;
    const d = Math.sqrt(((p1.x - p0.x) ** 2) + ((p1.y - p0.y) ** 2));
    const a = (((r0 ** 2) - (r1 ** 2)) + (d ** 2)) / (2 * d);
    const h = Math.sqrt(Math.abs((r0 ** 2) - (a ** 2)));

    // P2 = P0 + a * (P1 - P0) / d
    if (this.isInverse) {
      const tmp = p0;
      p0 = p1;
      p1 = tmp;
    }
    const p2 = {
      x: p0.x + ((a * (p1.x - p0.x)) / d),
      y: p0.y + ((a * (p1.y - p0.y)) / d),
    };
    const result = {
      px: p2.x + ((h * (p1.y - p0.y)) / d),
      py: p2.y - ((h * (p1.x - p0.x)) / d),
      nx: p2.x - ((h * (p1.y - p0.y)) / d),
      ny: p2.y + ((h * (p1.x - p0.x)) / d),
    };

    return result;
  }

  setCoords(side, type, x, y) {
    this.datum[side][`${type}x`] = x;
    this.datum[side][`${type}y`] = y;
  }

/**
 * Opens or closes the desired side of the link, changing between the min and max coordinates.
 * @param {boolean} isSource Selects which side to change coordinates, true if source
 * , false if target.
 * @param {boolean} toOpen Chooses if the coordinates should be switched to the
 * minimum (closed) or maximum (open).
 */
  switchSideCoords(isSource, toOpen) {
    if (isSource) {
      this.currCoords.x1 = toOpen ? this.datum.source.x : this.datum.source.mx;
      this.currCoords.y1 = toOpen ? this.datum.source.y : this.datum.source.my;
    } else {
      this.currCoords.x2 = toOpen ? this.datum.target.x : this.datum.target.mx;
      this.currCoords.y2 = toOpen ? this.datum.target.y : this.datum.target.my;
    }
    this.selection.attr('points', this.getPointsString());
    this.positionIndex();
  }

/**
 * Gets current coordinates as a svg points attribute ready string.
 */
  getPointsString() {
    const pos1 = this.isInverse ? 0 : 1;
    const pos2 = this.isInverse ? 1 : 0;
    return `${this.currCoords.x1},${this.currCoords.y1} ${(lineDivide[pos1] * this.currCoords.x1) + (lineDivide[pos2] * this.currCoords.x2)},${
      (lineDivide[pos1] * this.currCoords.y1) + (lineDivide[pos2] * this.currCoords.y2)} ${this.currCoords.x2},${this.currCoords.y2} `;
  }

  incrementCoords(side, x, y) {
    this.setCoords(side, 'm', this.datum[side].mx + x, this.datum[side].my + y);
    this.setCoords(side, '', this.datum[side].x + x, this.datum[side].y + y);

    if (side === 'source') {
      this.currCoords.x1 += x;
      this.currCoords.y1 += y;
    } else {
      this.currCoords.x2 += x;
      this.currCoords.y2 += y;
    }

    this.selection.attr('points', this.getPointsString());
  }

/**
 * Switches between regular link and forwarding path link modes.
 * @param {boolean} graphOn 
 * @param {*} conf A configuration object usually to initialize the fwgraph path
 * options.
 */
  toggleGraphMode(graphOn, conf) {
    this.graphMode = graphOn;
    if (this.graphMode) {
      if (conf) {
        this.isWarn = conf.isWarn;
        this.isError = conf.isError;
        this.isInverse = this.isInverse || conf.isInverse;
        if (this.isInverse) {
          this.datum.graphsourceid = this.datum.target.id;
          this.datum.graphtargetid = this.datum.source.id;
        }
      }
      this.selection.attr('marker-mid', `url(#arrow${this.isError ? '-error' : ''}${this.isWarn ? '-warn' : ''}${this.isInverse ? '-inverse' : ''})`);
      this.selection.classed(FWPATH_SEL.WARN, this.isWarn);
      this.selection.classed(FWPATH_SEL.ERROR, this.isError);
    } else {
      this.selection.attr('marker-mid', null);
      this.selection.classed(FWPATH_SEL.WARN, false);
      this.selection.classed(FWPATH_SEL.ERROR, false);
    }
    this.indexText.classed(FWPATH_SEL.INDEX_HIDDEN, !this.graphMode);
  }

  resetLink() {
    this.datum.graphsourceid = this.datum.source.id;
    this.datum.graphtargetid = this.datum.target.id;
    this.toggleGraphMode(false);
    this.clearIndexes();
  }

  setWarning(isWarning) {
    this.datum.isWarn = isWarning;
    this.isWarn = isWarning;
    this.selection.classed(FWPATH_SEL.WARN, this.isWarn);
    this.selection.attr('marker-mid', `url(#arrow-warn${this.isInverse ? '-inverse' : ''})`);
  }
}

export default LinkSelectionWrapper;

