(function () {
  function emitFieldEvents(field) {
    field.dispatchEvent(new Event("change", { bubbles: true }));
    field.dispatchEvent(new Event("keyup", { bubbles: true }));
  }

  function prefillAnalysisForm(trigger) {
    const ticker = trigger.dataset.analysisTicker;
    const tradeDate = trigger.dataset.analysisDate;
    const tickerInput = document.getElementById("analysis-ticker");
    const dateInput = document.getElementById("analysis-date");

    if (tickerInput && ticker) {
      tickerInput.value = ticker;
      emitFieldEvents(tickerInput);
    }
    if (dateInput && tradeDate) {
      dateInput.value = tradeDate;
      emitFieldEvents(dateInput);
    }
  }

  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-analysis-ticker]");
    if (!trigger) {
      return;
    }
    prefillAnalysisForm(trigger);
  });
})();
