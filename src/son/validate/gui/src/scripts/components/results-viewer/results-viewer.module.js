import angular from 'angular';
import { ResultsViewerComponent } from './results-viewer.component';
import { SearchInputComponent } from './search-input.component';
import { ResultsListComponent } from './results-list/results-list.component';
import { MenuCardComponent } from './results-list//menu-card.component';
import { filterItems } from './menu-items.filter';

export const ResultsViewerModule = angular.module('resultsViewer', [])
    .component('svResults', ResultsViewerComponent)
    .component('svSearchInput', SearchInputComponent)
    .component('svResList', ResultsListComponent)
    .component('svMenuCard', MenuCardComponent)
    .filter('fwgFilter', filterItems)
    .name;

export default ResultsViewerModule;
