$(document).ready(function() {
  const noResultsRow = "<tr id='noResultsRow'><td colspan='5'>No results found</td></tr>";

  $("#searchInput").on("input", function() {
    const value = $(this).val().toLowerCase();
    let visibleRowCount = 0;

    $("tbody tr").each(function() {
      const statusCell = $(this).find("td:eq(4)");
      const shouldShow = statusCell.text().toLowerCase().indexOf(value) > -1;

      if (shouldShow) {
        visibleRowCount++;
      }

      $(this).toggle(shouldShow);
    });

    $("#noResultsRow").remove();

    if (visibleRowCount === 0) {
      $("tbody").append(noResultsRow);
    }
  });
});