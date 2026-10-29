// Вага та обов’язковість доступні тільки для реально вибраної вимоги.
(() => {
  const mapping = {
    budget: ['budget_min', 'budget_max'], location: ['city', 'district'],
    move_in: ['move_in_date'],
    sleep: ['req_sleep'], cleanliness: ['req_min_cleanliness'],
    noise: ['req_max_noise'], guests: ['req_guests'],
    smoking: ['req_smoking'], pets: ['req_pets'], chores: ['req_chores']
  };
  const isSelected = (field) => field && !['', 'any'].includes(field.value.trim());
  const form = document.querySelector('form[data-loading]');
  if (!form) return;
  const summary = document.getElementById('criteria-active-summary');
  const cityInput = form.elements.city;
  const districtInput = form.elements.district;
  const locationData = document.getElementById('district-suggestions-data');
  const cityData = document.getElementById('city-suggestions-data');
  const districts = locationData ? JSON.parse(locationData.textContent) : {};
  const cities = cityData ? JSON.parse(cityData.textContent) : [];
  const normalize = value => value.trim().toLocaleLowerCase('uk');
  const unique = values => [...new Set(values.filter(Boolean))].sort((a,b) => a.localeCompare(b, 'uk'));
  let districtWidget;

  // Власний комбінований список: пошук + вибір + довільне значення.
  function makeCombo(input, optionsProvider) {
    if (!input) return null;
    const wrapper = document.createElement('div');
    wrapper.className = 'rm-combobox';
    input.parentNode.insertBefore(wrapper, input);
    wrapper.append(input);
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-expanded', 'false');
    const menu = document.createElement('div');
    menu.className = 'rm-combobox-menu';
    menu.setAttribute('role','listbox');
    menu.hidden = true;
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'rm-combobox-toggle';
    toggle.setAttribute('aria-label', 'Показати варіанти');
    toggle.textContent = '▾';
    wrapper.append(toggle, menu);
    let highlighted = -1;
    let values = [];
    function close() { menu.hidden=true; input.setAttribute('aria-expanded','false'); highlighted=-1; }
    function choose(value) {
      input.value = value;
      input.dispatchEvent(new Event('input',{bubbles:true}));
      input.dispatchEvent(new Event('change',{bubbles:true}));
      close(); input.focus();
    }
    function render(filter=true) {
      values = unique(optionsProvider()).filter(value => !filter || normalize(value).includes(normalize(input.value)));
      menu.replaceChildren(); highlighted=-1;
      if (!values.length) {
        const empty=document.createElement('div');
        empty.className='rm-combobox-empty';
        empty.textContent='Немає варіантів — введіть власний';
        menu.append(empty);
      } else values.forEach(value => {
        const option = document.createElement('button');
        option.type='button'; option.className='rm-combobox-option';
        option.setAttribute('role','option'); option.textContent=value;
        option.addEventListener('mousedown', event => event.preventDefault());
        option.addEventListener('click', () => choose(value));
        menu.append(option);
      });
      menu.hidden=false; input.setAttribute('aria-expanded','true');
    }
    input.addEventListener('focus', () => render(false));
    input.addEventListener('input', () => render(true));
    toggle.addEventListener('click', () => menu.hidden ? (input.focus(),render(false)) : close());
    input.addEventListener('keydown', e => {
      if (e.key === 'Escape') {close();return;}
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault(); if (menu.hidden) render(false);
        if (!values.length) return;
        highlighted=(highlighted+(e.key==='ArrowDown'?1:-1)+values.length)%values.length;
        [...menu.querySelectorAll('.rm-combobox-option')].forEach((el,i)=>el.classList.toggle('is-highlighted',i===highlighted));
        menu.children[highlighted]?.scrollIntoView({block:'nearest'});
      }
      if (e.key === 'Enter' && !menu.hidden && highlighted>=0) {e.preventDefault();choose(values[highlighted]);}
    });
    document.addEventListener('pointerdown', e => { if (!wrapper.contains(e.target)) close(); });
    return {close, refresh: () => {if (!menu.hidden) render(false);}};
  }
  makeCombo(cityInput, () => cities);
  districtWidget = makeCombo(districtInput, () => {
    const city=normalize(cityInput?.value||'');
    const matched=Object.entries(districts).find(([name])=>normalize(name)===city);
    return matched ? matched[1] : [];
  });
  if (cityInput && districtInput) {
    let lastCity=normalize(cityInput.value);
    cityInput.addEventListener('input', () => {
      const current=normalize(cityInput.value);
      if (current!==lastCity) {districtInput.value='';lastCity=current;districtWidget?.close();}
    });
  }
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
      if (status) status.textContent = enabled ? '' : 'Не вибрано';
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
