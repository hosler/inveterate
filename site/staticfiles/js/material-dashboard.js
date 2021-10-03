/*!

 =========================================================
 * Material Dashboard Dark PRO - v1.0.1
 =========================================================

 * Product Page: https://www.creative-tim.com/product/material-dashboard-dark-pro
 * Copyright 2020 Creative Tim (http://www.creative-tim.com)

 * Designed by www.invisionapp.com Coded by www.creative-tim.com

 =========================================================

 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

 */


var breakCards = true;

var searchVisible = 0;
var transparent = true;

var transparentDemo = true;
var fixedTop = false;

var mobile_menu_visible = 0,
  mobile_menu_initialized = false,
  toggle_initialized = false,
  bootstrap_nav_initialized = false;

var seq = 0,
  delays = 80,
  durations = 500;
var seq2 = 0,
  delays2 = 80,
  durations2 = 500;

var collapse = $('.collapse');

$(document).ready(function() {
  var isWindows = navigator.platform.indexOf('Win') > -1 ? true : false;

  if (isWindows) {
    // if we are on windows OS we activate the perfectScrollbar function

    if ($(".main-panel").length != 0) {
      var mainpanel = document.querySelector('.main-panel');
      var ps = new PerfectScrollbar(mainpanel);
    };
    if ($(".sidebar").length != 0) {
      var sidebar = document.querySelector('.sidebar');
      var ps1 = new PerfectScrollbar(sidebar);
    };
    if ($(".sidebar-wrapper").length != 0) {
      var sidebarwrapper = document.querySelector('.sidebar-wrapper');
      var ps2 = new PerfectScrollbar(sidebarwrapper);
    };
    if ($(".dropdown-menu").length != 0) {
      var dropdownmenu = document.querySelector('.dropdown-menu');
      var ps3 = new PerfectScrollbar(dropdownmenu);
    };
    if ($(".page-header").length != 0) {
      var pageheader = document.querySelector('.page-header');
      var ps4 = new PerfectScrollbar(pageheader);
    };

    $('html').addClass('perfect-scrollbar-on');
  } else {
    $('html').addClass('perfect-scrollbar-off');
  };


  $sidebar = $('.sidebar');
  window_width = $(window).width();

  $('body').bootstrapMaterialDesign({
    autofill: false
  });

  md.initSidebarsCheck();

  window_width = $(window).width();

  // check if there is an image set for the sidebar's background
  md.checkSidebarImage();

  md.initMinimizeSidebar();

  // Multilevel Dropdown menu

  $('.dropdown-menu a.dropdown-toggle').on('click', function(e) {
    var $el = $(this);
    var $parent = $(this).offsetParent(".dropdown-menu");
    if (!$(this).next().hasClass('show')) {
      $(this).parents('.dropdown-menu').first().find('.show').removeClass("show");
    }
    var $subMenu = $(this).next(".dropdown-menu");
    $subMenu.toggleClass('show');

    $(this).closest("a").toggleClass('open');

    $(this).parents('a.dropdown-item.dropdown.show').on('hidden.bs.dropdown', function(e) {
      $('.dropdown-menu .show').removeClass("show");
    });

    if (!$parent.parent().hasClass('navbar-nav')) {
      $el.next().css({
        "top": $el[0].offsetTop,
        "left": $parent.outerWidth() - 4
      });
    }

    return false;
  });

  // hide the siblings opened collapse

  collapse.on('show.bs.collapse', function() {
    $(this).parent().siblings().children('.collapse').each(function() {
      $(this).collapse('hide');
    });
  });

  //   Activate bootstrap-select
  if ($(".selectpicker").length != 0) {
    $(".selectpicker").selectpicker();
  }

  //  Activate the tooltips
  if ($('[data-toggle="tooltip"]').length != 0) {
    $('[data-toggle="tooltip"]').tooltip();
  }

  // Activate Popovers
  if ($('[data-toggle="popover"]').length != 0) {
    $('[data-toggle="popover"]').popover();
  }

  //Activate tags
  // we style the badges with our colors
  var tagClass = $('.tagsinput').data('color');

  if ($(".tagsinput").length != 0) {
    $('.tagsinput').tagsinput();
  }

  $('.bootstrap-tagsinput').addClass('' + tagClass + '-badge');

  //    Activate bootstrap-select
  $(".select").dropdown({
    "dropdownClass": "dropdown-menu",
    "optionClass": ""
  });

  $('.form-control').on("focus", function() {
    $(this).parent('.input-group').addClass("input-group-focus");
  }).on("blur", function() {
    $(this).parent(".input-group").removeClass("input-group-focus");
  });


  if (breakCards == true) {
    // We break the cards headers if there is too much stress on them :-)
    $('[data-header-animation="true"]').each(function() {
      var $fix_button = $(this)
      var $card = $(this).parent('.card');

      $card.find('.fix-broken-card').click(function() {
        console.log(this);
        var $header = $(this).parent().parent().siblings('.card-header, .card-header-image');

        $header.removeClass('hinge').addClass('animate__fadeInDown');

        $card.attr('data-count', 0);

        setTimeout(function() {
          $header.removeClass('animate__fadeInDown animate__animated');
        }, 480);
      });

      $card.mouseenter(function() {
        var $this = $(this);
        hover_count = parseInt($this.attr('data-count'), 10) + 1 || 0;
        $this.attr("data-count", hover_count);

        if (hover_count >= 20) {
          $(this).children('.card-header, .card-header-image').addClass('hinge animated');
        }
      });
    });
  }

  // remove class has-error for checkbox validation
  $('input[type="checkbox"][required="true"], input[type="radio"][required="true"]').on('click', function() {
    if ($(this).hasClass('error')) {
      $(this).closest('div').removeClass('has-error');
    }
  });

});

$(document).on('click', '.navbar-toggler', function() {
  $toggle = $(this);

  if (mobile_menu_visible == 1) {
    $('html').removeClass('nav-open');

    $('.close-layer').remove();
    setTimeout(function() {
      $toggle.removeClass('toggled');
    }, 400);

    mobile_menu_visible = 0;
  } else {
    setTimeout(function() {
      $toggle.addClass('toggled');
    }, 430);

    var $layer = $('<div class="close-layer"></div>');

    if ($('body').find('.main-panel').length != 0) {
      $layer.appendTo(".main-panel");

    } else if (($('body').hasClass('off-canvas-sidebar'))) {
      $layer.appendTo(".wrapper-full-page");
    }

    setTimeout(function() {
      $layer.addClass('visible');
    }, 100);

    $layer.click(function() {
      $('html').removeClass('nav-open');
      mobile_menu_visible = 0;

      $layer.removeClass('visible');

      setTimeout(function() {
        $layer.remove();
        $toggle.removeClass('toggled');

      }, 400);
    });

    $('html').addClass('nav-open');
    mobile_menu_visible = 1;

  }

});

// activate collapse right menu when the windows is resized
$(window).resize(function() {
  md.initSidebarsCheck();

  // reset the seq for charts drawing animations
  seq = seq2 = 0;

  setTimeout(function() {
    md.initDashboardPageCharts();
  }, 500);
});

md = {
  misc: {
    navbar_menu_visible: 0,
    active_collapse: true,
    disabled_collapse_init: 0,
  },

  checkSidebarImage: function() {
    $sidebar = $('.sidebar');
    image_src = $sidebar.data('image');

    if (image_src !== undefined) {
      sidebar_container = '<div class="sidebar-background" style="background-image: url(' + image_src + ') "/>';
      $sidebar.append(sidebar_container);
    }
  },

  showNotification: function(from, align) {
    type = ['', 'info', 'danger', 'success', 'warning', 'rose', 'primary'];

    color = Math.floor((Math.random() * 6) + 1);

    $.notify({
      icon: "add_alert",
      message: "Welcome to <b>Material Dashboard Pro</b> - a beautiful admin panel for every web developer."

    }, {
      type: type[color],
      timer: 3000,
      placement: {
        from: from,
        align: align
      }
    });
  },

  initDocumentationCharts: function() {
    if ($('#dailySalesChart').length != 0 && $('#websiteViewsChart').length != 0) {
      /* ----------==========     Daily Sales Chart initialization For Documentation    ==========---------- */

      dataDailySalesChart = {
        labels: ['M', 'T', 'W', 'T', 'F', 'S', 'S'],
        series: [
          [12, 17, 7, 17, 23, 18, 38]
        ]
      };

      optionsDailySalesChart = {
        lineSmooth: Chartist.Interpolation.cardinal({
          tension: 0
        }),
        low: 0,
        high: 50, // creative tim: we recommend you to set the high sa the biggest value + something for a better look
        chartPadding: {
          top: 0,
          right: 0,
          bottom: 0,
          left: 0
        },
      }

      var dailySalesChart = new Chartist.Line('#dailySalesChart', dataDailySalesChart, optionsDailySalesChart);

      var animationHeaderChart = new Chartist.Line('#websiteViewsChart', dataDailySalesChart, optionsDailySalesChart);
    }
  },


  initFormExtendedDatetimepickers: function() {
    $('.datetimepicker').datetimepicker({
      icons: {
        time: "fa fa-clock-o",
        date: "fa fa-calendar",
        up: "fa fa-chevron-up",
        down: "fa fa-chevron-down",
        previous: 'fa fa-chevron-left',
        next: 'fa fa-chevron-right',
        today: 'fa fa-screenshot',
        clear: 'fa fa-trash',
        close: 'fa fa-remove'
      }
    });

    $('.datepicker').datetimepicker({
      format: 'MM/DD/YYYY',
      icons: {
        time: "fa fa-clock-o",
        date: "fa fa-calendar",
        up: "fa fa-chevron-up",
        down: "fa fa-chevron-down",
        previous: 'fa fa-chevron-left',
        next: 'fa fa-chevron-right',
        today: 'fa fa-screenshot',
        clear: 'fa fa-trash',
        close: 'fa fa-remove'
      }
    });

    $('.timepicker').datetimepicker({
      //          format: 'H:mm',    // use this format if you want the 24hours timepicker
      format: 'h:mm A', //use this format if you want the 12hours timpiecker with AM/PM toggle
      icons: {
        time: "fa fa-clock-o",
        date: "fa fa-calendar",
        up: "fa fa-chevron-up",
        down: "fa fa-chevron-down",
        previous: 'fa fa-chevron-left',
        next: 'fa fa-chevron-right',
        today: 'fa fa-screenshot',
        clear: 'fa fa-trash',
        close: 'fa fa-remove'

      }
    });
  },


  initSliders: function() {
    // Sliders for demo purpose
    var slider = document.getElementById('sliderRegular');

    noUiSlider.create(slider, {
      start: 40,
      connect: [true, false],
      range: {
        min: 0,
        max: 100
      }
    });

    var slider2 = document.getElementById('sliderDouble');

    noUiSlider.create(slider2, {
      start: [20, 60],
      connect: true,
      range: {
        min: 0,
        max: 100
      }
    });
  },

  initSidebarsCheck: function() {
    if ($(window).width() <= 991) {
      if ($sidebar.length != 0) {
        md.initRightMenu();
      }
    }
  },

  checkFullPageBackgroundImage: function() {
    $page = $('.full-page');
    image_src = $page.data('image');

    if (image_src !== undefined) {
      image_container = '<div class="full-page-background" style="background-image: url(' + image_src + ') "/>'
      $page.append(image_container);
    }
  },

  initDashboardPageCharts: function() {

    if ($('#dailySalesChart').length != 0 || $('#completedTasksChart').length != 0 || $('#websiteViewsChart').length != 0) {
      /* ----------==========     Daily Sales Chart initialization    ==========---------- */

      dataDailySalesChart = {
        labels: ['M', 'T', 'W', 'T', 'F', 'S', 'S'],
        series: [
          [12, 17, 7, 17, 23, 18, 38]
        ]
      };

      optionsDailySalesChart = {
        lineSmooth: Chartist.Interpolation.cardinal({
          tension: 0
        }),
        low: 0,
        high: 50, // creative tim: we recommend you to set the high sa the biggest value + something for a better look
        chartPadding: {
          top: 0,
          right: 0,
          bottom: 0,
          left: 0
        },
      }

      var dailySalesChart = new Chartist.Line('#dailySalesChart', dataDailySalesChart, optionsDailySalesChart);

      md.startAnimationForLineChart(dailySalesChart);



      /* ----------==========     Completed Tasks Chart initialization    ==========---------- */

      dataCompletedTasksChart = {
        labels: ['12p', '3p', '6p', '9p', '12p', '3a', '6a', '9a'],
        series: [
          [230, 750, 450, 300, 280, 240, 200, 190]
        ]
      };

      optionsCompletedTasksChart = {
        lineSmooth: Chartist.Interpolation.cardinal({
          tension: 0
        }),
        low: 0,
        high: 1000, // creative tim: we recommend you to set the high sa the biggest value + something for a better look
        chartPadding: {
          top: 0,
          right: 0,
          bottom: 0,
          left: 0
        }
      }

      var completedTasksChart = new Chartist.Line('#completedTasksChart', dataCompletedTasksChart, optionsCompletedTasksChart);

      // start animation for the Completed Tasks Chart - Line Chart
      md.startAnimationForLineChart(completedTasksChart);


      /* ----------==========     Emails Subscription Chart initialization    ==========---------- */

      var dataWebsiteViewsChart = {
        labels: ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'],
        series: [
          [542, 443, 320, 780, 553, 453, 326, 434, 568, 610, 756, 895]

        ]
      };
      var optionsWebsiteViewsChart = {
        axisX: {
          showGrid: false
        },
        low: 0,
        high: 1000,
        chartPadding: {
          top: 0,
          right: 5,
          bottom: 0,
          left: 0
        }
      };
      var responsiveOptions = [
        ['screen and (max-width: 640px)', {
          seriesBarDistance: 5,
          axisX: {
            labelInterpolationFnc: function(value) {
              return value[0];
            }
          }
        }]
      ];
      var websiteViewsChart = Chartist.Bar('#websiteViewsChart', dataWebsiteViewsChart, optionsWebsiteViewsChart, responsiveOptions);

      //start animation for the Emails Subscription Chart
      md.startAnimationForBarChart(websiteViewsChart);
    }
  },

  initMinimizeSidebar: function() {

    $('#minimizeSidebar').click(function() {
      var $btn = $(this);

      if (md.misc.sidebar_mini_active == true) {
        $('body').removeClass('sidebar-mini');
        md.misc.sidebar_mini_active = false;
      } else {
        $('body').addClass('sidebar-mini');
        md.misc.sidebar_mini_active = true;
      }

      // we simulate the window Resize so the charts will get updated in realtime.
      var simulateWindowResize = setInterval(function() {
        window.dispatchEvent(new Event('resize'));
      }, 180);

      // we stop the simulation of Window Resize after the animations are completed
      setTimeout(function() {
        clearInterval(simulateWindowResize);
      }, 1000);
    });
  },

  checkScrollForTransparentNavbar: debounce(function() {
    if ($(document).scrollTop() > 260) {
      if (transparent) {
        transparent = false;
        $('.navbar-color-on-scroll').removeClass('navbar-transparent');
      }
    } else {
      if (!transparent) {
        transparent = true;
        $('.navbar-color-on-scroll').addClass('navbar-transparent');
      }
    }
  }, 17),


  initRightMenu: debounce(function() {
    $sidebar_wrapper = $('.sidebar-wrapper');

    if (!mobile_menu_initialized) {
      $navbar = $('nav').find('.navbar-collapse').children('.navbar-nav');

      mobile_menu_content = '';

      nav_content = $navbar.html();

      nav_content = '<ul class="nav navbar-nav nav-mobile-menu">' + nav_content + '</ul>';

      navbar_form = $('nav').find('.navbar-form').get(0).outerHTML;

      $sidebar_nav = $sidebar_wrapper.find(' > .nav');

      // insert the navbar form before the sidebar list
      $nav_content = $(nav_content);
      $navbar_form = $(navbar_form);
      $nav_content.insertBefore($sidebar_nav);
      $navbar_form.insertBefore($nav_content);

      $(".sidebar-wrapper .dropdown .dropdown-menu > li > a").click(function(event) {
        event.stopPropagation();

      });

      // simulate resize so all the charts/maps will be redrawn
      window.dispatchEvent(new Event('resize'));

      mobile_menu_initialized = true;
    } else {
      if ($(window).width() > 991) {
        // reset all the additions that we made for the sidebar wrapper only if the screen is bigger than 991px
        $sidebar_wrapper.find('.navbar-form').remove();
        $sidebar_wrapper.find('.nav-mobile-menu').remove();

        mobile_menu_initialized = false;
      }
    }
  }, 200),

  startAnimationForLineChart: function(chart) {

    chart.on('draw', function(data) {
      if (data.type === 'line' || data.type === 'area') {
        data.element.animate({
          d: {
            begin: 600,
            dur: 700,
            from: data.path.clone().scale(1, 0).translate(0, data.chartRect.height()).stringify(),
            to: data.path.clone().stringify(),
            easing: Chartist.Svg.Easing.easeOutQuint
          }
        });
      } else if (data.type === 'point') {
        seq++;
        data.element.animate({
          opacity: {
            begin: seq * delays,
            dur: durations,
            from: 0,
            to: 1,
            easing: 'ease'
          }
        });
      }
    });

    seq = 0;
  },
  startAnimationForBarChart: function(chart) {

    chart.on('draw', function(data) {
      if (data.type === 'bar') {
        seq2++;
        data.element.animate({
          opacity: {
            begin: seq2 * delays2,
            dur: durations2,
            from: 0,
            to: 1,
            easing: 'ease'
          }
        });
      }
    });

    seq2 = 0;
  },

  showSwal: function(type) {
    if (type == 'basic') {
      Swal.fire({
        title: 'Here is a message!',
        confirmButtonClass: "btn btn-success"
      })
    } else if (type == 'title-and-text') {

      Swal.fire({
        title: 'Here\'s a message!',
        text: 'It\'s pretty, isn\'t it?',
        confirmButtonClass: "btn btn-info"
      })
    } else if (type == 'success-message') {

      Swal.fire({
        icon: 'success',
        title: 'Good job!',
        showConfirmButton: false,
        timer: 1500
      })

    } else if (type == 'warning-message-and-confirmation') {
      Swal.fire({
        title: 'Are you sure?',
        text: "You won't be able to revert this!",
        icon: 'warning',
        showCancelButton: true,
        customClass: {
          confirmButton: 'btn btn-success',
          cancelButton: 'btn btn-danger'
        },
        confirmButtonText: 'Yes, delete it!'
      }).then(function(result) {
        if (result.value) {
          Swal.fire(
            'Deleted!',
            'Your file has been deleted.',
            'success'
          )
        }
      })
    } else if (type == 'warning-message-and-cancel') {
      var swalWithBootstrapButtons = Swal.mixin({
        customClass: {
          confirmButton: 'btn btn-success',
          cancelButton: 'btn btn-danger'
        },
        buttonsStyling: false
      })

      swalWithBootstrapButtons.fire({
        title: 'Are you sure?',
        text: "You won't be able to revert this!",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Yes, delete it!',
        cancelButtonText: 'No, cancel!',
        reverseButtons: true
      }).then(function(result) {
        if (result.value) {
          swalWithBootstrapButtons.fire(
            'Deleted!',
            'Your file has been deleted.',
            'success'
          )
        } else if (
          /* Read more about handling dismissals below */
          result.dismiss === Swal.DismissReason.cancel
        ) {
          swalWithBootstrapButtons.fire(
            'Cancelled',
            'Your imaginary file is safe ;)',
            'error'
          )
        }
      })
    } else if (type == 'custom-html') {
      Swal.fire({
        title: 'HTML example',
        icon: 'info',
        html: 'You can use <b>bold text</b>, ' +
          '<a href="javascript:;">links</a> ' +
          'and other HTML tags',
        showCloseButton: true,
        showCancelButton: true,
        focusConfirm: false,
        focusCancel: false,
        confirmButtonText: '<i class="fa fa-thumbs-up"></i> Great!',
        confirmButtonAriaLabel: 'Thumbs up, great!',
        cancelButtonText: '<i class="fa fa-thumbs-down"></i>',
        cancelButtonAriaLabel: 'Thumbs down'
      })
    } else if (type == 'auto-close') {
      Swal.fire({
        title: 'Auto close alert!',
        html: 'I will close in <strong></strong> milliseconds.',
        timer: 2000,
        onBeforeOpen: function() {
          Swal.showLoading()
          timerInterval = setInterval(function() {
            Swal.getContent().querySelector('strong')
              .textContent = Swal.getTimerLeft()
          }, 100)
        },
        onClose: function() {
          clearInterval(timerInterval)
        }
      }).then(function(result) {
        if (
          /* Read more about handling dismissals below */
          result.dismiss === Swal.DismissReason.timer
        ) {
          console.log('I was closed by the timer')
        }
      })
    } else if (type == 'input-field') {
      Swal.fire({
        title: 'Submit your Github username',
        input: 'text',
        inputAttributes: {
          autocapitalize: 'off'
        },
        showCancelButton: true,
        confirmButtonText: 'Look up',
        customClass: {
          confirmButton: 'btn btn-primary',
          cancelButton: 'btn btn-default'
        },
        buttonsStyling: false,
        showLoaderOnConfirm: true,
        preConfirm: function(login) {
          return fetch('//api.github.com/users/${login}')
            .then(function(response) {
              if (!response.ok) {
                throw new Error(response.statusText)
              }
              return response.json()
            })
            .catch(function(error) {
              Swal.showValidationMessage(
                'Request failed: ${error}'
              )
            })
        }
      }).then(function(result) {
        if (result.value) {
          Swal.fire({
            title: '${result.value.login}s avatar',
            imageUrl: result.value.avatar_url
          })
        }
      })
    }
  },

  initFullCalendar: function() {
    document.addEventListener('DOMContentLoaded', function() {
      var calendarEl = document.getElementById('fullCalendar');
      var today = new Date();
      var y = today.getFullYear();
      var m = today.getMonth();
      var d = today.getDate();
      var calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        selectable: true,
        headerToolbar: {
          left: 'title',
          center: 'dayGridMonth,timeGridWeek,timeGridDay',
          right: 'prev,next today'
        },
        select: function(info) {
          // on select we show the Sweet Alert modal with an input
          Swal.fire({
            title: 'Create an Event',
            html: '<div class="form-group">' +
              '<input class="form-control text-default" placeholder="Event Title" id="input-field">' +
              '</div>',
            showCancelButton: true,
            customClass: {
              confirmButton: 'btn btn-primary',
              cancelButton: 'btn btn-danger'
            },
            buttonsStyling: false
          }).then(function(result) {

            var eventData;
            event_title = $('#input-field').val();

            if (event_title) {
              eventData = {
                title: event_title,
                start: info.startStr,
                end: info.endStr
              };
              calendar.addEvent(eventData);
            }
          });
        },
        editable: true,
        // color classes: [ event-blue | event-azure | event-green | event-orange | event-red ]
        events: [{
            title: 'All Day Event',
            start: new Date(y, m, 1),
            className: 'event-default'
          },
          {
            id: 999,
            title: 'Repeating Event',
            start: new Date(y, m, d - 4, 6, 0),
            allDay: false,
            className: 'event-rose'
          },
          {
            id: 999,
            title: 'Repeating Event',
            start: new Date(y, m, d + 3, 6, 0),
            allDay: false,
            className: 'event-rose'
          },
          {
            title: 'Meeting',
            start: new Date(y, m, d - 1, 10, 30),
            allDay: false,
            className: 'event-green'
          },
          {
            title: 'Lunch',
            start: new Date(y, m, d + 7, 12, 0),
            end: new Date(y, m, d + 7, 14, 0),
            allDay: false,
            className: 'event-red'
          },
          {
            title: 'Md-pro Launch',
            start: new Date(y, m, d - 2, 12, 0),
            allDay: true,
            className: 'event-azure'
          },
          {
            title: 'Birthday Party',
            start: new Date(y, m, d + 1, 19, 0),
            end: new Date(y, m, d + 1, 22, 30),
            allDay: false,
            className: 'event-azure'
          },
          {
            title: 'Click for Creative Tim',
            start: new Date(y, m, 21),
            end: new Date(y, m, 22),
            url: 'http://www.creative-tim.com/',
            className: 'event-orange'
          },
          {
            title: 'Click for Google',
            start: new Date(y, m, 23),
            end: new Date(y, m, 23),
            url: 'http://www.creative-tim.com/',
            className: 'event-orange'
          }
        ]
      });
      calendar.render();
    });

  },

  initVectorMap: function() {
    var mapData = {
      "AU": 760,
      "BR": 550,
      "CA": 120,
      "DE": 1300,
      "FR": 540,
      "GB": 690,
      "GE": 200,
      "IN": 200,
      "RO": 600,
      "RU": 300,
      "US": 2920,
    };

    $('#worldMap').vectorMap({
      map: 'world_mill_en',
      backgroundColor: "transparent",
      zoomOnScroll: false,
      regionStyle: {
        initial: {
          fill: '#e4e4e4',
          "fill-opacity": 0.9,
          stroke: 'none',
          "stroke-width": 0,
          "stroke-opacity": 0
        }
      },

      series: {
        regions: [{
          values: mapData,
          scale: ["#AAAAAA", "#444444"],
          normalizeFunction: 'polynomial'
        }]
      },
    });
  }
}

// Returns a function, that, as long as it continues to be invoked, will not
// be triggered. The function will be called after it stops being called for
// N milliseconds. If `immediate` is passed, trigger the function on the
// leading edge, instead of the trailing.

function debounce(func, wait, immediate) {
  var timeout;
  return function() {
    var context = this,
      args = arguments;
    clearTimeout(timeout);
    timeout = setTimeout(function() {
      timeout = null;
      if (!immediate) func.apply(context, args);
    }, wait);
    if (immediate && !timeout) func.apply(context, args);
  };
};