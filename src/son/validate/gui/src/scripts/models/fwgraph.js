export class FwGraph {
  constructor(graph) {
    this.id = graph.fg_id;
    this.cycles = [];
    this.paths = [];
    this.collectParallels = [];
    this.formatGraph(graph);
    this.findParallels();
    this.hasErrors = Boolean(this.getAllLinks().find(link => link.isBreak));
    this.hasWarns = Boolean(this.cycles.length);
  }

  formatGraph(graph) {
    this.formatPaths(graph);
    if (graph.cycles) {
      this.formatCycles(graph.cycles);
    }
  }

  formatPaths(graph) {
    const paths = graph.fw_paths;

    paths.forEach((path, index) => {
      this.eventId = path.event_id;
      this.paths.push({
        id: path.fp_id,
        links: [...FwGraph.formatTrace(path.trace)],
        index,
      });
    });
  }

  static formatTrace(trace) {
    return trace.map((val, index) => ({
      id: val.from + val.to,
      source: val.from,
      target: val.to,
      index,
      isBreak: val.break,
    }));
  }

  static formatCycleLinks(path) {
    return path.map(val => ({
      id: val.from + val.to,
      source: val.from,
      target: val.to,
    }));
  }

  formatCycles(cycles) {
    cycles.forEach((cycle) => {
      this.cycles.push({
        id: cycle.cycle_id,
        links: [...FwGraph.formatCycleLinks(cycle.cycle_path)],
      });
    });
  }

  getAllLinks() {
    const coll = [];
    this.paths.forEach((path) => {
      coll.push(...path.links);
    });

    return coll;
  }

  findParallels() {
    const found = [];
    const unique = this.getAllLinks().filter((elem, index, array) => index === array.indexOf(elem));
    unique.forEach((un) => {
      unique.forEach((u) => {
        if (un.source === u.target && un.target === u.source) {
          un.hasParallel = true;
          u.hasParallel = true;
          found.push({
            p1: un,
            p2: u,
          });
        }
      });
    });
    this.collectParallels
      .push(...found.filter((elem, index, array) => index === array.indexOf(elem)));
  }
}

export default FwGraph;
