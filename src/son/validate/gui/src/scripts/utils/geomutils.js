function translatedCoords(node) {
  const baseVal = node.transform.baseVal;
  if (!baseVal.length) return { x: 0, y: 0 };

  const { e: x, f: y } = baseVal[0].matrix;
  return { x, y };
}

/**
 * Calculates the diagonal distance between 2 points
 * having into consideration translation coordinates.
 * @param {*} src Source coordinates.
 * @param {*} srcTranslate Source translated coordintes.
 * @param {*} tgt Target coordinates.
 * @param {*} tgtTranslate Target translated coordinates.
 */
function calcDiagonal(src, srcTranslate, tgt, tgtTranslate) {
  const x = (tgt.x + tgtTranslate.x) - (src.x + srcTranslate.x);
  const y = (tgt.y + tgtTranslate.y) - (src.y + srcTranslate.y);

  return Math.sqrt((x * x) + (y * y));
}

function getSlotById(slots, id) {
  return id && slots.find(slot => slot.filled === id);
}

// ELEMENTS
export function pairCoords(src, tgt) {
  if (src.empty() || tgt.empty()) return null;

  let sCoords;
  let tCoords;
  let levelDiff;
  const sDatum = src.datum();
  const tDatum = tgt.datum();

  /**
   * 0 -> same level
   * -1 -> source is parent
   * 1 -> source is child
   */
  if (sDatum.level === tDatum.level) {
    sCoords = translatedCoords(src.node());
    tCoords = translatedCoords(tgt.node());
    levelDiff = 0;
  } else if (sDatum.level < tDatum.level) {
    sCoords = { x: 0, y: 0 };
    tCoords = translatedCoords(tgt.node());
    levelDiff = -1;
  } else {
    sCoords = translatedCoords(src.node());
    tCoords = { x: 0, y: 0 };
    levelDiff = 1;
  }

  return {
    target: tCoords,
    source: sCoords,
    diff: levelDiff,
  };
}

/**
 * Finds the quadrant of the target relative to the source.
 * @param {*} source Source coordinates.
 * @param {*} target Target coordinates.
 */
export function getQuadrant(source, target) {
  const { x: sx, y: sy } = source;
  const { x: tx, y: ty } = target;

  let res;
  if (tx > sx) {
    if (ty > sy) res = 4;
    else res = 2;
  } else if (ty > sy) res = 3;
  else res = 1;

  return res;
}

export function getAvailable(slots) {
  return slots.find(slot => !slot.filled);
}

/**
 * Finds the optimal slots in the source and target nodes
 * to place both ends of the link.
 * @param {*} source Source node.
 * @param {*} target Target node.
 * @param {*} link The link to be connected.
 */
export function findClosestSlots(source, target, link) {
  if (!source || !target) return null;
  /**
   * 0 - same level
   * -1 - source is parent
   * 1 - source is child
   */
  const { source: scoords, target: tcoords, diff } = pairCoords(source, target);
  const sourcePositions = source.datum().conPositions;
  const targetPositions = target.datum().conPositions;

  let pickSource = getSlotById(sourcePositions, link.source);
  let pickTarget = getSlotById(targetPositions, link.target);
  if (pickSource && pickTarget) {
    return {
      source: pickSource,
      target: pickTarget,
      diff,
    };
  }

  let lockSource = true;
  let lockTarget = true;

  if (!pickSource) {
    pickSource = getAvailable(sourcePositions);
    lockSource = false;
  }
  if (!pickTarget) {
    pickTarget = getAvailable(targetPositions);
    lockTarget = false;
  }

  let oDiag = calcDiagonal(pickSource, scoords, pickTarget, tcoords);

  if (lockSource) {
    targetPositions.filter(cn => !cn.filled).forEach((tElement) => {
      const cDiag = calcDiagonal(pickSource, scoords, tElement, tcoords);
      if (cDiag < oDiag) {
        pickTarget = tElement;
        oDiag = calcDiagonal(pickSource, scoords, pickTarget, tcoords);
      }
    });
  } else if (lockTarget) {
    sourcePositions.filter(cn => !cn.filled).forEach((sElement) => {
      const cDiag = calcDiagonal(sElement, scoords, pickTarget, tcoords);
      if (cDiag < oDiag) {
        pickSource = sElement;
        oDiag = calcDiagonal(pickSource, scoords, pickTarget, tcoords);
      }
    });
  } else {
    sourcePositions.filter(cn => !cn.filled).forEach((sElement) => {
      targetPositions.filter(cn => !cn.filled).forEach((tElement) => {
        const cDiag = calcDiagonal(sElement, scoords, tElement, tcoords);
        if (cDiag < oDiag) {
          pickSource = sElement;
          pickTarget = tElement;
          oDiag = calcDiagonal(pickSource, scoords, pickTarget, tcoords);
        }
      });
    });
  }

  pickSource.filled = link.source;
  pickTarget.filled = link.target;

  return {
    source: pickSource,
    target: pickTarget,
    sIndex: sourcePositions.indexOf(pickSource),
    tIndex: targetPositions.indexOf(pickTarget),
    diff,
  };
}

export default {
  pairCoords,
  translatedCoords,
  getAvailable,
};
