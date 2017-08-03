import template from './app.html';
import { FwGraph } from './../models/fwgraph';
import { GRAPH_EVENT, HIGHLIGHT_EVENT,
  MANAGEMENT_EVENT, EXPAND_EVENT,
  LEVEL_EVENT, LOADING_EVENT, MODAL_EVENT } from '../services/event-strings';

const MESSAGES = {
  NO_TOPO: 'No topology validation to show.',
  INVALID_TOPO: 'Multiple network services not supported.',
};

export const AppComponent = {
  template,
  controller: class AppComponent {
    constructor($scope, $timeout, ValidatorService, StateService) {
      'ngInject';

      this.scope = $scope;
      this.timeout = $timeout;
      this.stateService = StateService;
      this.validatorService = ValidatorService;
      this.hideModal = true;
      this.id = '';
      this.path = '';
      this.errors = [];
      this.warnings = [];
      this.fwgraphs = [];
    }

    bindEvents() {
      this.scope.$on(MODAL_EVENT, () => {
        this.hideModal = false;
      });

      this.scope.$on(HIGHLIGHT_EVENT.EMIT, (event, data) => {
        this.scope.$broadcast(HIGHLIGHT_EVENT.CAST, data);
      });

      this.scope.$on(MANAGEMENT_EVENT.EMIT, (event, data) => {
        this.scope.$broadcast(MANAGEMENT_EVENT.CAST, data);
      });

      this.scope.$on(EXPAND_EVENT.EMIT, (event, data) => {
        this.scope.$broadcast(EXPAND_EVENT.CAST, data);
      });

      this.scope.$on(LEVEL_EVENT.EMIT, (event, data) => {
        this.scope.$broadcast(LEVEL_EVENT.CAST, data);
      });

      this.scope.$on(GRAPH_EVENT.EMIT, (event, data) => {
        this.scope.$broadcast(GRAPH_EVENT.CAST, data);
      });
    }

    $onInit() {
      this.bindEvents();
      this.scope.$watch(() => this.id, (newVal) => {
        if (newVal) {
          this.validatorService.getReportResult(newVal)
            .then((reports) => {
              this.errors = [...AppComponent.parseObject(reports, 'errors')];
              this.warnings = [...AppComponent.parseObject(reports, 'warnings')];
              this.stateService.setCurrentItem({ id: newVal, path: this.path });
              this.scope.$broadcast(LOADING_EVENT, {
                isLoading: true,
                isInvalid: false,
                message: '',
              });

              this.validatorService.getReportTopology(newVal)
                .then((topology) => {
                  const isInvalid = AppComponent.checkTopoValidity(topology);
                  if (!isInvalid) {
                    this.topology = topology;
                    this.validatorService.getReportFWGraphs(newVal)
                      .then((fwgraphs) => {
                        this.fwgraphs = [];
                        fwgraphs.forEach((fwg) => {
                          this.fwgraphs.push(new FwGraph(fwg));
                        });
                      });
                  } else {
                    this.scope.$broadcast(LOADING_EVENT, {
                      isInvalid,
                      isLoading: false,
                      message: MESSAGES.INVALID_TOPO,
                    });

                    this.errors = [];
                    this.warnings = [];
                  }
                })
                .catch(() => {
                  this.timeout(() => {
                    this.topology = null;
                    this.scope.$broadcast(LOADING_EVENT, {
                      isloading: false,
                      isInvalid: true,
                      message: MESSAGES.NO_TOPO,
                    });
                  }, 500);
                });
            });
        }
      });

      const storedItem = this.stateService.getStoredItem();
      if (storedItem) {
        this.id = storedItem.id;
        this.path = storedItem.path;
      } else {
        this.hideModal = false;
      }
    }

    static checkTopoValidity(topology) {
      const filtered = topology.nodes.filter(node => node.level === '0');
      const nodeIds = [];
      if (filtered.length > 0) {
        filtered.forEach((fil) => {
          if (nodeIds.indexOf(fil.node_id) < 0) nodeIds.push(fil.node_id);
        });
      }

      return nodeIds.length > 1;
    }

    onValidationSelect(validation) {
      this.id = validation.id;
      this.path = validation.path;
    }

    closeModal(toClose) {
      this.hideModal = toClose;
    }

    static parseObject(obj, type) {
      const parsed = [];

      if (obj[type]) {
        obj[type].forEach((ele) => {
          const found = parsed.find(p => p.sourceId === ele.source_id);
          const details = [];
          ele.detail.forEach((det) => {
            details.push({
              eventId: det.detail_event_id,
              message: det.message,
            });
          });
          if (found) {
            found.events.push({
              eventCode: ele.event_code,
              eventId: ele.event_id,
              header: ele.header,
              details,
            });
          } else {
            const newObjectId = {
              sourceId: ele.source_id,
              events: [{
                eventCode: ele.event_code,
                eventId: ele.event_id,
                header: ele.header,
                details,
              }],
            };
            parsed.push(newObjectId);
          }
        });
      }

      return parsed;
    }
  },
};

export default AppComponent;
