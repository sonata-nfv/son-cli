import { identity } from 'angular';
import { API, TOKENS } from './api-strings';
import { parseXML } from '../utils/parser';

/* global FormData */

export class ValidatorService {
  constructor($http) {
    'ngInject';

    this.http = $http;
  }

  postValidate(type, validation) {
    const formData = new FormData();
    formData.append('source', validation.source);
    formData.append('path', validation.path);
    formData.append('syntax', validation.syntax);
    formData.append('integrity', validation.integrity);
    formData.append('topology', validation.topology);
    formData.append('file', validation.file);

    return this.http({
      url: API.validate.replace(TOKENS.type, type),
      method: 'POST',
      data: formData,
      transformRequest: identity,
      headers: { 'Content-Type': undefined },
    }).then(response => response.data);
  }

  getReports() {
    return this.http.get(API.report.list)
      .then(response => response.data);
  }

  getReportResult(id) {
    return this.http.get(API.report.single.result.replace(TOKENS.id, id))
      .then(response => response.data);
  }

  getReportTopology(id) {
    return parseXML(API.report.single.topology.replace(TOKENS.id, id));
  }

  getReportFWGraphs(id) {
    return this.http.get(API.report.single.fwgraph.replace(TOKENS.id, id))
      .then(response => response.data);
  }

  getResources() {
    return this.http.get(API.resources);
  }

  getWatches() {
    return this.http.get(API.watches);
  }
}

export default ValidatorService;
