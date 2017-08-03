/**
 * Directive that allows Angular and D3 interaction.
 */
import * as d3 from 'd3';
import * as SVGFactory from './element.factory';
import * as CONF from './viewer-conf';
import { Topology } from '../../models/topology';
import { Link } from '../../models/link';
import { findClosestSlots, pairCoords, getQuadrant } from '../../utils/geomutils';
import { MANAGEMENT_EVENT, HIGHLIGHT_EVENT,
  LEVEL_EVENT, EXPAND_EVENT } from '../../services/event-strings';

export const ViewerDirective = () => {
  const allLinks = [];
  const views = {
    bridgeless: {},
    bridgeful: {},
  };
  let svg;
  let zoomGroup;
  let popupWindow;
  let zoom;
  let height;
  let width;
  let errors = [];
  let warnings = [];
  let fwgraph;

/**
 * Creates and appends links to the SVG
 * @param {*[]} nodes Array of all nodes.
 * @param {*[]} link Array of links.
 */
  function makeLink(nodes, link) {
    const srcNode = nodes.filter(datum => datum.connections
      .find(con => con.id === link.source));
    const tgtNode = nodes.filter(datum => datum.connections
      .find(con => con.id === link.target));

    const pair = findClosestSlots(srcNode, tgtNode, link);
    if (pair.source && pair.target) {
      let selection = tgtNode;
      if (pair.diff !== undefined) {
        switch (pair.diff) {
          case 0:
            selection = d3.select(tgtNode.node().parentNode);
            break;
          case -1:
            selection = srcNode;
            break;
          case 1:
            selection = d3.select(srcNode.node().parentNode);
            break;
          default:
        }
      }

      const { source: tsrc, target: ttgt } = pairCoords(srcNode, tgtNode);
      const nLink = new Link(link.label, link.source,
        pair.source.x + tsrc.x, pair.source.y + tsrc.y,
        (pair.source.mx ? pair.source.mx : pair.source.x) + tsrc.x,
        (pair.source.my ? pair.source.my : pair.source.y) + tsrc.y,
        link.target,
        pair.target.x + ttgt.x,
        pair.target.y + ttgt.y,
        (pair.target.mx ? pair.target.mx : pair.target.x) + ttgt.x,
        (pair.target.my ? pair.target.my : pair.target.y) + ttgt.y);

      const newLink = SVGFactory.makeLink(selection, nLink);
      allLinks.push(newLink);
      const allIfaces = d3.selectAll(`rect.${CONF.IFACE_SEL.BASE}`);
      const srcIface = allIfaces.filter(d => d.filled === nLink.source.id);
      const tgtIface = allIfaces.filter(d => d.filled === nLink.target.id);

      nLink.source.id && srcIface.empty() && SVGFactory
        .makeInterface(srcNode, pair.source, pair.sIndex);
      nLink.target.id && tgtIface.empty() && SVGFactory
        .makeInterface(tgtNode, pair.target, pair.tIndex);

      return newLink;
    }

    return null;
  }

  /**
   * Pulls apart links that may be on top of each other
   * allowing a clean visualization of forwarding paths.
   */
  function pullParallels() {
    allLinks.forEach((linkA) => {
      allLinks.forEach((linkB) => {
        if (linkA.datum.isParallel(linkB.datum)) {
          const quadrant = getQuadrant(linkA.datum.source, linkA.datum.target);
          let offsetX1;
          let offsetY1;
          let offsetX2;
          let offsetY2;
          const constant = 5;
          if (quadrant === 1 || quadrant === 4) {
            offsetX1 = constant;
            offsetY1 = -constant;
            offsetX2 = -constant;
            offsetY2 = constant;
          } else {
            offsetX1 = -constant;
            offsetY1 = -constant;
            offsetX2 = constant;
            offsetY2 = constant;
          }
          linkA.incrementCoords('source', offsetX1, offsetY1);
          linkA.incrementCoords('target', offsetX1, offsetY1);

          linkB.incrementCoords('source', offsetX2, offsetY2);
          linkB.incrementCoords('target', offsetX2, offsetY2);
        }
      });
    });
  }

/**
 * Creates and appends the forwarding graph's elements to the SVG.
 * @param {*} graph The forwarding graph to be drawn.
 */
  function makeGraph(graph) {
    allLinks.forEach((link) => {
      link.resetLink();
    });
    const allNodes = d3.selectAll(`.${CONF.NODE_SEL.BASE}`);
    graph.collectParallels.forEach((parallel) => {
      const foundP1 = allLinks.find(link => link.isGraphEqual(parallel.p1));
      const foundP2 = allLinks.find(link => link.isGraphEqual(parallel.p2));

      foundP1 && foundP1.toggleGraphMode(true, {
        isInverse: false, isError: false, isWarn: false,
      }, parallel.p1.hasParallel);

      foundP2 && foundP2.toggleGraphMode(true, {
        isInverse: false,
        isError: false,
        isWarn: false,
      }, parallel.p2.hasParallel);

      if (!foundP1) {
        const nBreak = makeLink(allNodes, parallel.p1);
        nBreak.graphOnly = true;
        nBreak.hasParallel = true;
      } else if (!foundP2) {
        const nBreak = makeLink(allNodes, parallel.p2);
        nBreak.graphOnly = true;
        nBreak.hasParallel = true;
      }
    });

    graph.paths.forEach((path) => {
      path.links.forEach((pathLink) => {
        const found = allLinks.find(link => link.isGraphEqual(pathLink));
        if (found) {
          found.toggleGraphMode(true, {
            isInverse: false,
            isError: false,
            isWarn: false,
          });
          found.setIndexesText(path.index);
        } else if (pathLink.isBreak) {
          const nBreak = makeLink(allNodes, pathLink);
          if (nBreak) {
            nBreak.graphOnly = true;
            nBreak.toggleGraphMode(true, {
              isInverse: false,
              isError: true,
              isWarn: false,
            });
            nBreak.setIndexesText(path.index);
          }
        } else {
          const revFound = allLinks.find(link => link.isReverse(pathLink) && !link.hasParallel);
          if (revFound) {
            revFound.toggleGraphMode(true, {
              isInverse: true,
              isError: false,
              isWarn: false,
            });
            revFound.setIndexesText(path.index);
          }
        }
      });
    });

    graph.cycles.forEach((cycle) => {
      cycle.links.forEach((pLink) => {
        const found = allLinks.find(link => link.isGraphEqual(pLink));
        found && found.setWarning(true);
      });
    });

    allLinks.forEach((link) => {
      link.selection.classed(CONF.LINK_SEL.FADED, !link.graphMode);
    });
    pullParallels();
  }

  function clearTopology() {
    popupWindow && popupWindow.popup.remove();
    svg.selectAll('*').remove();
    allLinks.length = 0;
  }

  function setZoom() {
    const translate = [(width / 2), (height / 2)];

    svg.transition().duration(0)
      .call(zoom.transform,
      d3.zoomIdentity.translate(translate[0], translate[1]));
  }

  function highlightErrors() {
    errors.forEach((error) => {
      error.events.forEach((event) => {
        d3.selectAll(`.${CONF.NODE_SEL.BASE}`)
          .filter(d => d.id === event.eventId)
          .select(`.${CONF.SHAPE_SEL.BASE}`)
          .style('stroke', '#e03a3e');
      });
    });
  }

  function highlightWarnings() {
    warnings.forEach((warn) => {
      warn.events.forEach((event) => {
        d3.selectAll(`.${CONF.NODE_SEL.BASE}`)
          .filter(d => d.id === event.eventId)
          .select(`.${CONF.SHAPE_SEL.BASE}`)
          .each((d, index, group) => {
            const shape = d3.select(group[index]);
            (shape.style('stroke') !== d3.color('#e03a3e').toString()) && shape.style('stroke', '#cab000');
          });
      });
    });
  }

 /**
  * Searches the links array for the ones connected to the given node.
  * @param {*} node The node to which the links should be connected to
  * either as source or target.
  */
  function findLinksToNode(node) {
    const connections = node.datum().connections;
    const linked = [];

    allLinks.forEach((lnk) => {
      const found = connections.find(con => con.id === lnk.datum.source.id ||
        con.id === lnk.datum.target.id);
      if (found) {
        linked.push({
          element: lnk,
          isSource: found.id === lnk.datum.source.id,
        });
      }
    });

    return linked;
  }

  function openNode(node) {
    const datum = node.datum();
    const shape = node.select(`.${CONF.SHAPE_SEL.BASE}`);

    shape.attr('r', d => d.openRadius);
    node.classed(CONF.NODE_SEL.OPEN, true)
      .select(`.${CONF.LABEL_SEL.ID}`)
      .attr('y', d => -d.openRadius - 10);
    node.select(`.${CONF.LABEL_SEL.TYPE}`)
      .classed(CONF.LABEL_SEL.HIDDEN, true);

    const ifaces = d3.selectAll(`.${CONF.IFACE_SEL.BASE}`);
    datum.conPositions.forEach((conn) => {
      ifaces.filter(d => d.filled === conn.filled)
        .attr('transform', d => `translate(${d.x - (CONF.IFACE_DIM.WIDTH / 2)}, ${d.y - (CONF.IFACE_DIM.HEIGHT / 2)}) rotate(${d.rotate}, ${CONF.IFACE_DIM.WIDTH / 2}, ${CONF.IFACE_DIM.HEIGHT / 2})`);
    });

    const group = node.select(`.${CONF.ICON_SEL.GROUP}`)
      .attr('transform', d => `translate(${d.iconsPos.x},${d.iconsPos.y})`);

    group.select(`.${CONF.ICON_SEL.ZOOM_IN}`)
      .classed(CONF.ICON_SEL.HIDDEN, true);
    group.select(`.${CONF.ICON_SEL.ZOOM_OUT}`)
      .classed(CONF.ICON_SEL.HIDDEN, false);

    group.datum(() => null).select(`.${CONF.ICON_SEL.INFO}`)
      .attr('transform', d => `translate(${d.x}, ${d.y})`);

    findLinksToNode(node).forEach((linked) => {
      linked.element.switchSideCoords(linked.isSource, true);
    });
  }

  function closeNode(node) {
    const datum = node.datum();
    node.select(`.${CONF.SHAPE_SEL.BASE}`)
      .attr('r', d => d.closedRadius);

    node.classed(CONF.NODE_SEL.OPEN, false)
      .select(`.${CONF.LABEL_SEL.ID}`)
      .attr('y', d => -d.closedRadius - 10);
    node.select(`.${CONF.LABEL_SEL.TYPE}`)
      .classed(CONF.LABEL_SEL.HIDDEN, false);

    const group = node.select(`.${CONF.ICON_SEL.GROUP}`)
      .attr('transform', d => `translate(${d.iconsPos.mx},${d.iconsPos.my})`);
    group.datum(() => null).select(`.${CONF.ICON_SEL.INFO}`)
      .attr('transform', d => `translate(${d.mx}, ${d.y})`);
    group.select(`.${CONF.ICON_SEL.ZOOM_IN}`)
      .classed(CONF.ICON_SEL.HIDDEN, false);
    group.select(`.${CONF.ICON_SEL.ZOOM_OUT}`)
      .classed(CONF.ICON_SEL.HIDDEN, true);

    const ifaces = d3.selectAll(`.${CONF.IFACE_SEL.BASE}`);
    datum.conPositions.forEach((conn) => {
      ifaces.filter(d => d.filled === conn.filled)
        .attr('transform', d => `translate(${d.mx - (CONF.IFACE_DIM.WIDTH / 2)}, ${d.my - (CONF.IFACE_DIM.HEIGHT / 2)}) rotate(${d.index % 2 ? 45 : 0}, ${CONF.IFACE_DIM.WIDTH / 2}, ${CONF.IFACE_DIM.HEIGHT / 2})`);
    });

    findLinksToNode(node).forEach((linked) => {
      linked.element.switchSideCoords(linked.isSource, false);
    });
  }

  function togglePopup(datum, toOpen) {
    if (toOpen) {
      const tmpPop = popupWindow.popup.remove();
      d3.select(svg.node()).append(() => tmpPop.node());
      popupWindow.popup.attr('transform', `translate(${d3.mouse(svg.node())[0] - 60}, ${d3.mouse(svg.node())[1]})`);
      popupWindow.title.html(`<span class="${CONF.POPUP_SEL.TITLE}" title="${datum.id}">${datum.getType().toUpperCase()} ${datum.id}</span>`);
      popupWindow.text.html(`<span class="${CONF.POPUP_SEL.TEXT}">${datum.label}</span>`);
      popupWindow.popup.classed(CONF.POPUP_SEL.HIDDEN, !toOpen);
    }

    popupWindow.popup.classed(CONF.POPUP_SEL.HIDDEN, !toOpen);
  }

  function makeLinks(links) {
    const allNodes = d3.selectAll(`.${CONF.NODE_SEL.BASE}`);
    links.forEach((link) => {
      makeLink(allNodes, link);
    });
  }

  function makeLevels(data) {
    zoom = d3.zoom().scaleExtent([1 / 4, 8]).on('zoom', () => {
      zoomGroup.attr('transform', d3.event.transform);
    });

    svg.call(zoom);
    zoomGroup = svg.append('g');
    SVGFactory.makeDefs(svg);
    SVGFactory.makeLevel(zoomGroup, data.root.children,
      mouseoverHighlight, openNode, closeNode, togglePopup);
    makeLinks(data.links);
  }

  function zoomToFit() {
    const first = zoomGroup.select('g');
    const bwidth = svg.node().width.baseVal.value;
    const bheight = svg.node().height.baseVal.value;
    const { x: fx, y: fy, width: fwidth, height: fheight } = first.node().getBBox();
    const x = fx + (fwidth / 2);
    const y = fy + (fheight / 2);

    const maxWH = Math.min(8, 0.5 / Math.max(width / bwidth,
      height / bheight));

    const scale = Math.max(1 / 4, maxWH);
    const translate = [(bwidth / 2) - (scale * x), (bheight / 2) - (scale * y)];

    svg.transition().duration(100)
      .call(zoom.transform,
      d3.zoomIdentity.translate(translate[0], translate[1]).scale(scale));
  }

  function setEventBindings(scope) {
    scope.$on(MANAGEMENT_EVENT.CAST, (event, data) => {
      clearTopology();
      const view = data ? views.bridgeful : views.bridgeless;
      makeLevels(view);
      setZoom();
      highlightErrors();
      highlightWarnings();
      fwgraph && makeGraph(fwgraph);
    });

    scope.$on(HIGHLIGHT_EVENT.CAST, (event, data) => {
      const nodes = d3.selectAll(`.${CONF.NODE_SEL.BASE}`);
      if (data.id.length === 0) {
        nodes.select(`.${CONF.SHAPE_SEL.BASE}`)
          .style('stroke-width', null);
      } else {
        const foundPath = fwgraph.paths.find(path => path.id === data.id);
        foundPath && foundPath.links.forEach((link) => {
          const found = allLinks.find(alink => alink.isGraphEqual(link));
          found && found.selection.style('stroke-width', data.hlight ? 5 : null);
        });

        const foundCycle = fwgraph.cycles.find(cycle => cycle.id === data.id);
        foundCycle && foundCycle.links.forEach((link) => {
          const found = allLinks.find(alink => alink.isGraphEqual(link));
          found && found.selection.style('stroke-width', data.hlight ? 5 : null);
        });
        nodes.select(`.${CONF.SHAPE_SEL.BASE}`)
          .style('stroke-width', null);
        nodes.filter(d => (data.search ? d.id.includes(data.id)
          || d.label.includes(data.id) : d.id === data.id))
          .select(`.${CONF.SHAPE_SEL.BASE}`)
          .style('stroke-width', data.hlight ? 10 : null);
      }
    });

    scope.$on(LEVEL_EVENT.CAST, (event, data) => {
      d3.selectAll(`.${CONF.NODE_SEL.PARENT}`).each((datum, index, group) => {
        const toggleNode = datum.level < data ? openNode : closeNode;
        toggleNode(d3.select(group[index]));
      });
    });

    scope.$on(EXPAND_EVENT.CAST, (event, data) => {
      d3.selectAll(`.${CONF.NODE_SEL.PARENT}`).each((datum, index, group) => {
        const toggleNode = data ? openNode : closeNode;
        toggleNode(d3.select(group[index]));
        data && zoomToFit();
      });
    });
  }

  function setWatchers(scope, element) {
    scope.$watch('topology', (nVal) => {
      const root = d3.select(element);
      clearTopology();
      if (nVal) {
        views.bridgeful = new Topology(nVal.nodes, nVal.links, false);
        views.bridgeless = new Topology(nVal.nodes, nVal.links, true);
        makeLevels(views.bridgeful);
        setZoom();
        setEventBindings(scope, root);
        popupWindow = SVGFactory.makePopup(svg, togglePopup);
      } else if (nVal === null && scope.isInvalid) {
        SVGFactory.makeNoTopology(svg, width, height, scope.message);
        views.bridgeful = {};
        views.bridgeless = {};
      }
    });

    scope.$watch('errors', (value) => {
      if (value) {
        errors = [];
        errors.push(...value);
        highlightErrors();
      }
    });

    scope.$watch('warnings', (value) => {
      if (value) {
        warnings = [];
        warnings.push(...value);
        highlightWarnings();
      }
    });

    scope.$watch('fwgraph', (value) => {
      fwgraph = value;
      fwgraph && makeGraph(fwgraph);
    });

    scope.$watch('fwgraph.isActive', (value) => {
      if (fwgraph) {
        fwgraph.getAllLinks().forEach((link) => {
          const found = allLinks.find(allLink => allLink.isGraphEqual(link));
          found && found.toggleGraphMode(value);
        });
        allLinks.forEach((aLink) => {
          if (aLink.graphOnly) {
            aLink.group.classed(CONF.LINK_SEL.GROUP_HIDDEN, !value);
            aLink.indexText.classed(CONF.FWPATH_SEL.INDEX_HIDDEN, !value);
          } else {
            aLink.selection.classed(CONF.LINK_SEL.FADED, !aLink.graphMode && value);
          }
        });
      }
    });
  }

  function init(scope, element) {
    height = element.clientHeight;
    width = element.clientWidth;
    svg = d3.select(element)
      .append('svg')
      .attr('width', width)
      .attr('height', height);
    setWatchers(scope, svg);
  }

  function mouseoverHighlight(node, toLight) {
    d3.event.stopPropagation();
    const parent = d3.select(node.node().parentNode);

    parent.classed(CONF.NODE_SEL.BASE) && mouseoverHighlight(parent, false);

    node.select(`.${CONF.ICON_SEL.GROUP}`)
      .classed(CONF.ICON_SEL.GROUP_HIDDEN, !toLight)
      .selectAll(`.${CONF.ICON_SEL.SHAPE}`)
      .classed(CONF.ICON_SEL.SHAPE_HIGHLIGHT, toLight);

    node.select(`.${CONF.SHAPE_SEL.BASE}`)
      .classed(CONF.SHAPE_SEL.HIGHLIGHT, toLight);
    d3.selectAll(node.node().children)
      .filter((d, index, group) => d3.select(group[index]).classed(CONF.IFACE_SEL.BASE))
      .classed(CONF.IFACE_SEL.HIGHLIGHT, toLight);
  }

  return {
    restrict: 'A',
    link(scope, element) {
      init(scope, element[0]);
    },
  };
};

export default ViewerDirective;
