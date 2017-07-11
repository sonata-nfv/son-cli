export const FileOnChange = () => {
  return {
    restrict: 'A',
    link(scope, element) {
      element.on('change', (event) => {
        if (scope.files.length > 0) {
          scope.files.splice(0, 1, event.target.files[0]);
        } else {
          scope.files.push(event.target.files[0]);
        }
        scope.$apply();
      });
    },
  };
};

export default FileOnChange;
