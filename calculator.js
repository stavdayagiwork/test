'use strict';

let chartInstance = null;

const ILS = new Intl.NumberFormat('he-IL', { style: 'currency', currency: 'ILS', maximumFractionDigits: 0 });

function formatCurrency(n) {
  return ILS.format(Math.round(n));
}

function getInputs() {
  const currentAge    = parseInt(document.getElementById('currentAge').value, 10);
  const retirementAge = parseInt(document.getElementById('retirementAge').value, 10);
  const initial       = parseFloat(document.getElementById('initial').value)    || 0;
  const monthly       = parseFloat(document.getElementById('monthly').value)    || 0;
  const annualRate    = parseFloat(document.getElementById('annualRate').value)  || 0;
  const inflationRaw  = document.getElementById('inflationRate').value.trim();
  const inflationRate = inflationRaw === '' ? 0 : (parseFloat(inflationRaw) || 0);

  if (isNaN(currentAge) || isNaN(retirementAge)) {
    return { error: 'נא להזין גיל נוכחי וגיל יעד תקינים.' };
  }
  if (currentAge < 1 || retirementAge > 100) {
    return { error: 'הגיל חייב להיות בין 1 ל-100.' };
  }
  if (currentAge >= retirementAge) {
    return { error: 'גיל הפרישה חייב להיות גדול מהגיל הנוכחי.' };
  }
  if (initial < 0 || monthly < 0) {
    return { error: 'סכומי ההשקעה אינם יכולים להיות שליליים.' };
  }

  return { currentAge, retirementAge, initial, monthly, annualRate, inflationRate };
}

function calculateYearlyData(inputs) {
  const { currentAge, retirementAge, initial, monthly, annualRate, inflationRate } = inputs;
  const monthlyRate = annualRate / 100 / 12;
  const useInflation = inflationRate > 0;

  let balance = initial;
  const data = [];

  for (let age = currentAge; age <= retirementAge; age++) {
    const yearsElapsed = age - currentAge;

    if (age === currentAge) {
      // snapshot at start (no compounding yet, just the lump sum)
      const totalInvested = initial;
      const portfolioValue = initial;
      const interestEarned = 0;
      const realValue = useInflation
        ? portfolioValue / Math.pow(1 + inflationRate / 100, yearsElapsed)
        : portfolioValue;
      data.push({ age, totalInvested, portfolioValue, interestEarned, realValue });
      continue;
    }

    // compound monthly for one full year
    for (let m = 0; m < 12; m++) {
      balance = balance * (1 + monthlyRate) + monthly;
    }

    const totalInvested = initial + monthly * 12 * yearsElapsed;
    const portfolioValue = balance;
    const interestEarned = portfolioValue - totalInvested;
    const realValue = useInflation
      ? portfolioValue / Math.pow(1 + inflationRate / 100, yearsElapsed)
      : portfolioValue;

    data.push({ age, totalInvested, portfolioValue, interestEarned, realValue });
  }

  return data;
}

function renderStats(data, inputs) {
  const last = data[data.length - 1];
  document.getElementById('stat-invested').textContent = formatCurrency(last.totalInvested);
  document.getElementById('stat-final').textContent    = formatCurrency(last.portfolioValue);
  document.getElementById('stat-gain').textContent     = formatCurrency(last.interestEarned);

  const realCard = document.getElementById('stat-real-card');
  if (inputs.inflationRate > 0) {
    realCard.classList.remove('hidden');
    document.getElementById('stat-real').textContent = formatCurrency(last.realValue);
  } else {
    realCard.classList.add('hidden');
  }
}

function renderTable(data, inputs) {
  const tbody = document.getElementById('breakdown-body');
  tbody.innerHTML = '';

  const showReal = inputs.inflationRate > 0;
  document.querySelectorAll('.col-real').forEach(el => {
    el.classList.toggle('hidden', !showReal);
  });

  const lastAge = data[data.length - 1].age;
  const fragment = document.createDocumentFragment();

  data.forEach(row => {
    const tr = document.createElement('tr');
    if (row.age === lastAge) tr.classList.add('retirement-row');

    tr.innerHTML = `
      <td>${row.age}</td>
      <td>${formatCurrency(row.totalInvested)}</td>
      <td>${formatCurrency(row.portfolioValue)}</td>
      <td>${formatCurrency(row.interestEarned)}</td>
      <td class="col-real${showReal ? '' : ' hidden'}">${formatCurrency(row.realValue)}</td>
    `;
    fragment.appendChild(tr);
  });

  tbody.appendChild(fragment);
}

function renderChart(data, inputs) {
  const labels  = data.map(d => `${d.age}`);
  const values  = data.map(d => d.portfolioValue);
  const invested = data.map(d => d.totalInvested);
  const real    = data.map(d => d.realValue);

  const datasets = [
    {
      label: 'שווי תיק ההשקעות',
      data: values,
      borderColor: '#2563eb',
      backgroundColor: 'rgba(37,99,235,0.08)',
      fill: true,
      tension: 0.35,
      pointRadius: data.length > 40 ? 0 : 3,
    },
    {
      label: 'סך הפקדות',
      data: invested,
      borderColor: '#16a34a',
      backgroundColor: 'rgba(22,163,74,0.05)',
      borderDash: [6, 4],
      fill: true,
      tension: 0.35,
      pointRadius: 0,
    },
  ];

  if (inputs.inflationRate > 0) {
    datasets.push({
      label: 'שווי ריאלי (מנוכה אינפלציה)',
      data: real,
      borderColor: '#dc2626',
      borderDash: [4, 4],
      fill: false,
      tension: 0.35,
      pointRadius: 0,
    });
  }

  const chartData = { labels, datasets };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        position: 'top',
        labels: { font: { family: 'Rubik, Arial, sans-serif', size: 13 } },
      },
      tooltip: {
        callbacks: {
          title: ctx => `גיל ${ctx[0].label}`,
          label: ctx => `${ctx.dataset.label}: ${formatCurrency(ctx.parsed.y)}`,
        },
      },
    },
    scales: {
      x: {
        title: { display: true, text: 'גיל', font: { family: 'Rubik, Arial, sans-serif' } },
        ticks: { font: { family: 'Rubik, Arial, sans-serif' } },
      },
      y: {
        ticks: {
          callback: val => formatCurrency(val),
          font: { family: 'Rubik, Arial, sans-serif', size: 11 },
        },
      },
    },
  };

  if (chartInstance) {
    chartInstance.data = chartData;
    chartInstance.options = options;
    chartInstance.update();
  } else {
    const ctx = document.getElementById('investmentChart').getContext('2d');
    chartInstance = new Chart(ctx, { type: 'line', data: chartData, options });
  }
}

function renderResults(data, inputs) {
  const resultsSection = document.getElementById('results');
  resultsSection.classList.remove('hidden');
  renderStats(data, inputs);
  renderTable(data, inputs);
  renderChart(data, inputs);
  resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('calculator-form');
  const errorEl = document.getElementById('form-error');

  form.addEventListener('submit', e => {
    e.preventDefault();
    errorEl.textContent = '';

    const inputs = getInputs();
    if (inputs.error) {
      errorEl.textContent = inputs.error;
      return;
    }

    const data = calculateYearlyData(inputs);
    renderResults(data, inputs);
  });
});
