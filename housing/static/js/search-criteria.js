// Вага та обов’язковість доступні тільки для реально вибраної вимоги.
(() => {
  const mapping = {
    budget: ['budget_min', 'budget_max'], location: ['city', 'district'],
    move_in: ['move_in_date'], age: ['req_age_min', 'req_age_max'],
    sleep: ['req_sleep'], cleanliness: ['req_min_cleanliness'],
    noise: ['req_max_noise'], guests: ['req_guests'],
    smoking: ['req_smoking'], pets: ['req_pets'], chores: ['req_chores']
  };
  const isSelected = (field) => field && !['', 'any'].includes(field.value.trim());
  const form = document.querySelector('form[data-loading]');
  if (!form) return;
  const summary = document.getElementById('criteria-active-summary');
  function update() {
    const active = [];
    document.querySelectorAll('tr[data-criterion]').forEach(row => {
      const key = row.dataset.criterion;
      const enabled = (mapping[key] || []).some(name => isSelected(form.elements[name]));
      const weight = form.elements[`w_${key}`];
      const critical = form.elements[`c_${key}`];
      if (!weight || !critical) return;
      weight.disabled = !enabled;
      critical.disabled = !enabled;
      if (!enabled) critical.checked = false;
      row.classList.toggle('criterion-inactive', !enabled);
      const label = row.querySelector('td')?.childNodes[0]?.textContent.trim() || key;
      const status = row.querySelector('.criterion-state');
      if (status) status.textContent = enabled ? 'Враховується в підборі' : 'Не вибрано — налаштування вимкнені';
      if (enabled) active.push({label, weight: weight.value, critical: critical.checked});
    });
    if (summary) {
      summary.replaceChildren();
      if (!active.length) {
        const item = document.createElement('li');
        item.textContent = 'Поки немає заданих вимог. Оберіть потрібні параметри вище.';
        summary.append(item);
      } else active.forEach(({label, weight, critical}) => {
        const item = document.createElement('li');
        item.textContent = `${label} — важливість ${weight} із 5${critical ? ', обов’язкова умова' : ''}`;
        summary.append(item);
      });
    }
  }
  form.addEventListener('input', update);
  form.addEventListener('change', update);
  update();
})();
