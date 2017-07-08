/**
 * This module contains all the methods needed to build the various elements
 *
 * of the visualizer. By passing a base element and the necessary datum a new
 *
 * svg element is added to the visualizer.
 */
import * as d3 from 'd3';
import * as CONF from './viewer-conf';
import { LinkSelectionWrapper } from './link-selection';
import iconClose from '../../../assets/icons/ic-close.svg';
import iconOut from '../../../assets/icons/ic-zoom-out.svg';
import iconIn from '../../../assets/icons/ic-zoom-in.svg';
import iconInfo from '../../../assets/icons/ic-info.svg';
import bridgeIcon from '../../../assets/icons/ic-switch.svg';

function getRadians(index, maxDivs, offset = 0) {
  return ((2 * Math.PI * index) / maxDivs) + (Math.PI * offset);
}

function radToX(index, maxDivs, offset) {
  return Math.cos(getRadians(index, maxDivs, offset));
}

function radToY(index, maxDivs, offset) {
  return Math.sin(getRadians(index, maxDivs, offset));
}

function findEmptyChildPosition(datum) {
  return datum.childPositions.find(slot => !slot.filled);
}

function slotsOnRect(node) {
  const slots = [];
  const { width, height } = node.select(`.${CONF.SHAPE_SEL.BASE}`).node().getBBox();
  const maxSlots = CONF.BRIDGE_COUNT.CONNECTIONS;
  const radWidth = width / 2;
  const radHeight = height / 2;

  for (let i = 0; i < maxSlots; i += 1) {
    const radius = i % 2 ? radHeight : radWidth;
    slots.push({
      x: radToX(i, maxSlots) * radius,
      y: radToY(i, maxSlots) * radius,
      mx: radToX(i, maxSlots) * radius,
      my: radToY(i, maxSlots) * radius,
      filled: null,
    });
  }

  return slots;
}

/**
 *
 * @param {*} node the node around which the slots are to be located.
 * @return {*[]} array of slots.
 */
function slotsOnCircle(node) {
  const slots = [];
  const datum = node.datum();
  const { width, height, x, y } = node.select(`.${CONF.SHAPE_SEL.BASE}`).node().getBBox();
  const maxSlots = CONF.SUM_COUNT.CONNECTIONS;
  const nChildren = datum.children.length;
  const minRadius = datum.level >= 1 ? CONF.SUM_DIM.SMALL : CONF.SUM_DIM.MEDIUM;
  let radius = nChildren ? 50 * nChildren : CONF.SUM_DIM.SMALL;

  if (datum.level === 0) radius = 150 * nChildren;

  for (let i = 0; i < maxSlots; i += 1) {
    slots.push({
      x: x + (width / 2) + (radToX(i, maxSlots, 0.5) * radius),
      y: y + (height / 2) + (radToY(i, maxSlots, 0.5) * radius),
      mx: x + (width / 2) + (radToX(i, maxSlots, 0.5) * minRadius),
      my: y + (height / 2) + (radToY(i, maxSlots, 0.5) * minRadius),
      filled: null,
    });
  }

  return slots;
}

/**
 *
 * @param {*} node the node inside which the children are to be placed.
 * @return {*[]} array of child positions.
 */
function childSlots(node) {
  const childrenArray = [];
  const datum = node.datum();
  const nChildren = datum.children.length;
  const { width, height, x, y } = node.select(`.${CONF.SHAPE_SEL.BASE}`).node().getBBox();
  const radius = datum.openRadius;

  if (nChildren === 1) {
    childrenArray.push({
      x: x + (width / 2),
      y: y + (height / 2),
      filled: false,
    });
  } else {
    for (let i = 0; i < nChildren; i += 1) {
      childrenArray.push({
        x: x + (width / 2) + (radToX(i, nChildren, 0.5) * (radius / 2)),
        y: y + (height / 2) + (radToY(i, nChildren, 0.5) * (radius / 2)),
        filled: false,
      });
    }
  }

  return childrenArray;
}

/**
 *
 * @param {*} base the base element to append to.
 * @param {*} width the width of the base element
 * @param {*} height the height of the base element
 * @param {*} message the message to display.
 */
export function makeNoTopology(base, width, height, message) {
  base
    .append('text')
    .classed(CONF.SVG_SEL.NO_TOPOLOGY, true)
    .text(message)
    .attr('text-anchor', 'middle')
    .attr('x', width / 2)
    .attr('y', height / 2);
}

export function makeLevel(base, data, mouseEventHandler,
  openNodeHandler, closeNodeHandler, infoNodeHandler) {
  base.selectAll()
    .data(data)
    .enter()
    .append('g')
    .attr('class', CONF.NODE_SEL.BASE)
    .classed(CONF.NODE_SEL.PARENT, d => d.children.length)
    .on('mouseover', (datum, index, group) => {
      mouseEventHandler(d3.select(group[index]), true);
    })
    .on('mouseleave', (datum, index, group) => {
      mouseEventHandler(d3.select(group[index]), false);
    })
    .each((datum, index, group) => {
      const ele = d3.select(group[index]);
      if (datum.type === 'sum') {
        this.makeSum(ele, openNodeHandler, closeNodeHandler, infoNodeHandler);
        this.makeIdText(ele);
      } else if (datum.type === 'bridge') {
        this.makeBridge(ele);
      }
      this.makeTypeText(ele);

      if (datum.level !== 0) {
        const found = d3.selectAll(`.${CONF.NODE_SEL.PARENT}`)
          .filter(d => d.id === base.datum().id && d.parentid === base.datum().parentid);
        const emptySlot = findEmptyChildPosition(found.datum());
        ele.attr('transform', `translate(${emptySlot.x}, ${emptySlot.y})`);
        emptySlot.filled = true;
      } else {
        ele.attr('transform', `translate(${Number(base.attr('width')) / 2},${Number(base.attr('height')) / 2})`);
      }

      this.makeLevel(ele, datum.children,
        mouseEventHandler,
        openNodeHandler,
        closeNodeHandler,
        infoNodeHandler);
    });
}

export function makeSum(base, openNodeHandler, closeNodeHandler, infoNodeHandler) {
  const nodeDatum = base.datum();
  const nChildren = nodeDatum.children.length;
  nodeDatum.closedRadius = nodeDatum.level < 1 ? CONF.SUM_DIM.MEDIUM : CONF.SUM_DIM.SMALL;
  nodeDatum.openRadius = nChildren ? 50 * nChildren : CONF.SUM_DIM.SMALL;
  if (nodeDatum.level === 0) nodeDatum.openRadius = 150 * nChildren;

  base.append('circle')
    .attr('class', d => `${CONF.SHAPE_SEL.BASE} ${d.level === 0 ? CONF.SHAPE_SEL.LV1 : CONF.SHAPE_SEL.LV2}`)
    .attr('r', d => d.closedRadius)
    .attr('cx', 0)
    .attr('cy', 0)
    .each(() => {
      this.makeIconsGroup(base, openNodeHandler, closeNodeHandler, infoNodeHandler);
    });
  nodeDatum.conPositions = slotsOnCircle(base);
  if (nodeDatum.children.length) nodeDatum.childPositions = childSlots(base);
}

export function makeBridge(base) {
  const datum = base.datum();
  datum.closedRadius = CONF.BRIDGE_DIM.HEIGHT;
  base.append('rect')
    .attr('class', CONF.SHAPE_SEL.BASE)
    .attr('x', 0 - (CONF.BRIDGE_DIM.WIDTH / 2))
    .attr('y', 0 - (CONF.BRIDGE_DIM.HEIGHT / 2))
    .attr('width', CONF.BRIDGE_DIM.WIDTH)
    .attr('height', CONF.BRIDGE_DIM.HEIGHT);
  base.append('svg:image')
    .attr('x', -12.5)
    .attr('y', -12.5)
    .attr('width', 25)
    .attr('height', 25)
    .attr('xlink:href', bridgeIcon);
  datum.conPositions = slotsOnRect(base);
}

export function makeInterface(base, datum, index) {
  datum.index = index;
  if (datum.filled.includes('br-mgmt')) {
    datum.rotate = 0;
  } else {
    datum.rotate = index % 2 ? 45 : 0;
  }

  base.insert('rect', `.${CONF.SHAPE_SEL.BASE}`)
    .datum(datum)
    .classed(`${CONF.IFACE_SEL.BASE}`, true)
    .attr('width', CONF.IFACE_DIM.WIDTH)
    .attr('height', CONF.IFACE_DIM.HEIGHT)
    .attr('transform', d => `translate(${d.mx - (CONF.IFACE_DIM.WIDTH / 2)}, ${d.my - (CONF.IFACE_DIM.HEIGHT / 2)}) rotate(${d.rotate}, ${CONF.IFACE_DIM.WIDTH / 2}, ${CONF.IFACE_DIM.HEIGHT / 2})`)
    .append('title')
    .text(d => d.filled);
}

export function makeLink(base, datum) {
  return new LinkSelectionWrapper(base, datum);
}

export function makeIndexText(base, datum) {
  base.insert('text', `g.${CONF.NODE_SEL.BASE}`)
    .datum(datum)
    .classed(CONF.FWPATH_SEL.INDEX, true)
    .attr('x', d => (d.source.mx + d.target.mx) / 2)
    .attr('y', d => (d.source.my + d.target.my) / 2)
    .text(d => d.pathIndexes.join(', '));
}

export function makeTypeText(base) {
  base.append('text')
    .classed(CONF.LABEL_SEL.TYPE, true)
    .attr('text-anchor', 'middle')
    .attr('x', 0)
    .attr('y', d => (d.level === 2 ? -5 : 4))
    .text(d => d.getType());
}

export function makeIdText(base) {
  base.append('text')
    .classed(CONF.LABEL_SEL.ID, true)
    .classed(CONF.LABEL_SEL.ID_L2, base.datum().level === 2)
    .attr('text-anchor', 'middle')
    .attr('x', 0)
    .attr('y', d => (d.level === 2 ? 10 : -(d.closedRadius + 10)))
    .text((d) => {
      const concat = d.label.length > 15 ? `${d.label.substring(0, 12)}...` : d.label;
      return `${concat}`;
    });
}

export function makeIcon(base, datum, type, iconClass = '', isHidden = false) {
  const icon = base.append('g')
    .datum(datum)
    .attr('transform', d => `translate(${d.mx !== undefined ? d.mx : d.x},${d.y})`)
    .attr('class', `${CONF.ICON_SEL.BASE} ${iconClass} ${isHidden ? CONF.ICON_SEL.HIDDEN : ''}`);
  icon.append('circle')
    .attr('class', CONF.ICON_SEL.SHAPE)
    .attr('r', 11)
    .attr('cx', 12)
    .attr('cy', 12);
  icon.append('svg:image')
    .attr('xlink:href', type)
    .attr('width', 14)
    .attr('height', 14)
    .attr('x', 5)
    .attr('y', 5);

  return icon;
}

export function makeIconsGroup(base, openNodeHandler, closeNodeHandler, infoNodeHandler) {
  const datum = base.datum();
  const nChildSlots = datum.children.length;
  const shape = base.select(`.${CONF.SHAPE_SEL.BASE}`);
  const { width, height, x, y } = shape.node().getBBox();
  const nDivs = 16;

  base.datum().iconsPos = {
    mx: x + (width / 2) + ((radToX(13, nDivs) * datum.closedRadius) - 5),
    my: y + (height / 2) + ((radToY(13, nDivs) * datum.closedRadius) - 5),
    x: x + (width / 2) + (radToX(13, nDivs) * datum.openRadius),
    y: y + (height / 2) + (radToY(13, nDivs) * datum.openRadius),
  };
  const group = base.append('g')
    .attr('class', `${CONF.ICON_SEL.GROUP} ${CONF.ICON_SEL.GROUP_HIDDEN}`)
    .attr('transform', d => `translate(${d.iconsPos.mx}, ${d.iconsPos.my})`);

  if (nChildSlots) {
    this.makeIcon(group, { x: 5, y: 0 }, iconIn, 'icon--zoom-in', false)
      .on('click', () => {
        openNodeHandler(base);
      });
    this.makeIcon(group, { x: 5, y: 0 }, iconOut, 'icon--zoom-out', true)
      .on('click', () => {
        closeNodeHandler(base);
      });
  }
  this.makeIcon(group, { mx: nChildSlots ? 20 : 10, x: nChildSlots ? 12.5 * nChildSlots : 5, y: 20 }, iconInfo, 'icon--info', false)
    .on('click', () => {
      infoNodeHandler(datum, true);
    }).on('mouseover', (d, index, eleGroup) => {
      d3.select(eleGroup[index]).select(`.${CONF.ICON_SEL.SHAPE}`)
        .classed(CONF.ICON_SEL.SHAPE_HOVER, true);
    }).on('mouseout', (d, index, eleGroup) => {
      d3.select(eleGroup[index]).select(`.${CONF.ICON_SEL.SHAPE}`)
        .classed(CONF.ICON_SEL.SHAPE_HOVER, false);
    });
}

export function makePopup(base, onClick) {
  const popup = base.append('g')
    .attr('class', `${CONF.POPUP_SEL.BASE} ${CONF.POPUP_SEL.HIDDEN}`);
  popup.append('rect')
    .attr('class', CONF.POPUP_SEL.FRAME)
    .attr('width', '260px')
    .attr('height', '325px')
    .attr('rx', '4px')
    .attr('ry', '4px');
  const title = popup.append('foreignObject')
    .attr('x', 10)
    .attr('y', 10)
    .attr('width', 220)
    .attr('height', 20);
  popup.append('svg:image')
    .attr('class', CONF.POPUP_SEL.ICON)
    .attr('xlink:href', iconClose)
    .attr('width', 16)
    .attr('height', 16)
    .attr('x', 232)
    .attr('y', 10)
    .on('click', () => {
      onClick(null, false);
    });

  const text = popup.append('foreignObject')
    .attr('x', 10)
    .attr('y', 30)
    .attr('width', 240)
    .attr('height', 305);

  return {
    popup,
    title,
    text,
  };
}

function makeDef(base, type, isInverse = false) {
  let selector;
  let id;
  if (type === 'normal') {
    selector = CONF.FWPATH_SEL.MARKER;
    id = 'arrow';
  } else if (type === 'error') {
    selector = CONF.FWPATH_SEL.MARKER_ERROR;
    id = 'arrow-error';
  } else {
    selector = CONF.FWPATH_SEL.MARKER_WARN;
    id = 'arrow-warn';
  }

  base.append('defs')
    .append('marker')
    .attr('id', `${id}${isInverse ? '-inverse' : ''}`)
    .attr('markerHeight', 6)
    .attr('markerWidth', 6)
    .attr('refX', 0)
    .attr('refY', 3)
    .attr('orient', 'auto')
    .attr('markerUnits', 'strokeWidth')
    .append('polyline')
    .attr('points', isInverse ? '6,0 3,3 6,6' : '0,0 3,3 0,6')
    .attr('class', selector);
}

export function makeDefs(base) {
  makeDef(base, 'normal');
  makeDef(base, 'error');
  makeDef(base, 'warn');
  makeDef(base, 'normal', true);
  makeDef(base, 'error', true);
  makeDef(base, 'warn', true);
}


export default {
  makeNoTopology,
  makeLevel,
  makeSum,
  makeBridge,
  makeInterface,
  makeLink,
  makeTypeText,
  makeIdText,
  makeIcon,
  makeIconsGroup,
  makePopup,
  makeDefs,
};
