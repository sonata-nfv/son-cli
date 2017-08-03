import template from './graph-selector.html';
import { GRAPH_EVENT } from '../../services/event-strings';

export const GraphSelectorComponent = {

  template,
  bindings: {
    graphs: '<',
    onSelect: '&',
  },
  controller: class GraphSelectorComponent {
    constructor($scope) {
      'ngInject';

      this.scope = $scope;
    }

    $onChanges(changesObj) {
      if (changesObj.graphs && changesObj.graphs.currentValue.length) {
        this.graphs[0].isActive = true;
      }
    }

    toggleGraph(graph, index) {
      this.setActive(index);
      this.onSelect({
        $event: {
          value: graph,
        },
      });
      this.scope.$emit(GRAPH_EVENT.EMIT, {
        id: graph.id,
        visible: graph.isActive,
      });
    }

    setActive(currentIndex) {
      this.graphs.forEach((element, index) => {
        if (index !== currentIndex) element.isActive = false;
        else if (index === currentIndex && element.isActive) element.isActive = false;
        else element.isActive = true;
      });
    }
  },
};

export default GraphSelectorComponent;
