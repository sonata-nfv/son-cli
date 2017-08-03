export function filterItems() {
  return (items, graphs) => {
    const filtered = [];

    items.forEach((element) => {
      const found = graphs.find(graph => element.sourceId.includes(graph.id));
      if (found) {
        if (found.isActive) {
          filtered.push(element);
        }
      } else {
        filtered.push(element);
      }
    });

    return filtered;
  };
}

export default filterItems;
