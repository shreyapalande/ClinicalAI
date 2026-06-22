const Router = {
  current: null,
  prev: null,

  go(page, id = null) {
    this.prev = this.current;
    this.current = page;
    document.querySelectorAll('.nav-links a').forEach(a => {
      a.classList.toggle('active', a.dataset.page === page);
    });
    if (page === 'patients') renderPatients();
    else if (page === 'patient' && id) renderPatientDetail(id);
    else if (page === 'record') renderRecord();
    else if (page === 'search') renderSearch();
    else renderPatients();
  },

  back() {
    if (this.prev === 'search') renderSearch(true);
    else renderPatients();
  },
};

// Nav link clicks
document.querySelectorAll('.nav-links a').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    Router.go(a.dataset.page);
  });
});

// Boot
Router.go('patients');
