/**
 * D3 XML parser adapted to SONATA's validator format.
 *
 * Parses each part separately (nodes, links, attributes)
 *
 * Joins necessary attributes with nodes and links.
 */
import { xml } from 'd3';

function xmlGetNodes(xmlDoc) {
  return [].map.call(xmlDoc.querySelectorAll('node'), (node) => {
    const data = [].map.call(node.querySelectorAll('data'), datum => ({
      key: datum.getAttribute('key'),
      value: datum.textContent,
    }));
    return {
      id: node.getAttribute('id'),
      data,
    };
  });
}

function xmlGetLinks(xmlDoc) {
  return [].map.call(xmlDoc.querySelectorAll('edge'), (link) => {
    const data = [].map.call(link.querySelectorAll('data'), datum => ({
      key: datum.getAttribute('key'),
      value: datum.textContent,
    }));
    return {
      source: link.getAttribute('source'),
      target: link.getAttribute('target'),
      data,
    };
  });
}

function xmlGetAttributes(xmlDoc) {
  return [].map.call(xmlDoc.querySelectorAll('key'), attr => ({
    id: attr.getAttribute('id'),
    name: attr.getAttribute('attr.name'),
    for: attr.getAttribute('for'),
  }));
}

function joinKeyDataNodes(items, keys) {
  const joined = [];

  items.forEach((item) => {
    const join = {};
    join.id = item.id;
    if (item.data) {
      item.data.forEach((datum) => {
        const key = keys.find(k => k.id === datum.key && k.for === 'node');
        join[key.name] = datum.value;
      });
    }

    joined.push(join);
  });

  return joined;
}

function joinKeyDataLinks(items, keys) {
  const joined = [];
  items.forEach((item) => {
    const join = {};
    join.source = item.source;
    join.target = item.target;
    if (item.data) {
      item.data.forEach((datum) => {
        const key = keys.find(k => k.id === datum.key && k.for === 'edge');
        join[key.name] = datum.value;
      });
    }

    joined.push(join);
  });

  return joined;
}

export function parseXML(file) {
  const promise = new Promise((resolve, reject) => {
    xml(file).mimeType('application/xml').get((error, xmlDoc) => {
      if (error) {
        reject(error);
        return;
      }

      const nodes = xmlGetNodes(xmlDoc);
      const links = xmlGetLinks(xmlDoc);
      const attributes = xmlGetAttributes(xmlDoc);

      const jnodes = joinKeyDataNodes(nodes, attributes);
      const jlinks = joinKeyDataLinks(links, attributes);

      resolve({ nodes: jnodes, links: jlinks });
    });
  });

  return promise;
}


export default parseXML;
