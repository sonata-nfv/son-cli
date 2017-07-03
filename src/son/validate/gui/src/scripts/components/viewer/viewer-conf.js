export const SUM_DIM = {
  MEDIUM: 60,
  SMALL: 35,
};

export const BRIDGE_DIM = {
  HEIGHT: 40,
  WIDTH: 70,
};

export const IFACE_DIM = {
  HEIGHT: 12,
  WIDTH: 12,
};

export const SUM_COUNT = {
  CONNECTIONS: 8,
  CHILDREN: 4,
};

export const BRIDGE_COUNT = {
  CONNECTIONS: 4,
};

export const SVG_SEL = {
  NO_TOPOLOGY: 'sv-viewer__no-topo',
};

export const POPUP_SEL = {
  BASE: 'sv-viewer__popup',
  HIDDEN: 'sv-viewer__popup--hidden',
  FRAME: 'popup__frame',
  ICON: 'popup__icon',
  TITLE: 'popup__title',
  TEXT: 'popup__text',
};

export const NODE_SEL = {
  BASE: 'node',
  OPEN: 'node--open',
  PARENT: 'node--with-children',
};

export const SHAPE_SEL = {
  BASE: 'node__shape',
  LV1: 'node__shape--level1',
  LV2: 'node__shape--level2',
  HIGHLIGHT: 'node__shape--highlight',
};

export const LABEL_SEL = {
  TYPE: 'node__text--type',
  HIDDEN: 'node__text--hidden',
  ID: 'node__text',
  ID_L2: 'node__text--l2',
};

export const ICON_SEL = {
  BASE: 'node__icon',
  ZOOM_OUT: 'icon--zoom-out',
  ZOOM_IN: 'icon--zoom-in',
  INFO: 'icon--info',
  HIDDEN: 'icon--hide',
  INTERMED: 'icon__intermediary',
  GROUP: 'icon__group',
  GROUP_HIDDEN: 'icon__group--hide',
  SHAPE: 'icon__shape',
  SHAPE_HIGHLIGHT: 'icon__shape--highlight',
  SHAPE_HOVER: 'icon__shape--hover',
};

export const IFACE_SEL = {
  BASE: 'node__iface',
  HIGHLIGHT: 'node__iface--highlight',
};

export const LINK_SEL = {
  BASE: 'link',
  GROUP: 'link__group',
  WARN: 'link--warning',
  ERROR: 'link--error',
  FADED: 'link--faded',
  HOVER: 'link--hovered',
  GROUP_HIDDEN: 'link__group--hidden',
};

export const FWPATH_SEL = {
  BASE: 'fwpath',
  INDEX: 'fwpath__index',
  INDEX_HOVERED: 'fwpath__index--hovered',
  INDEX_HIDDEN: 'fwpath__index--hidden',
  ERROR: 'fwpath--error',
  WARN: 'fwpath--warning',
  MARKER: 'fwpath__marker',
  MARKER_ERROR: 'fwpath__marker--error',
  MARKER_WARN: 'fwpath__marker--warn',
};

export default {
  IFACE_DIM,
  SUM_DIM,
  BRIDGE_DIM,
  BRIDGE_COUNT,
  SUM_COUNT,
  NODE_SEL,
  SHAPE_SEL,
  IFACE_SEL,
  LABEL_SEL,
  POPUP_SEL,
  SVG_SEL,
};
