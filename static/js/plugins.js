
// usage: log('inside coolFunc', this, arguments);
// paulirish.com/2009/log-a-lightweight-wrapper-for-consolelog/
window.log = function(){
  log.history = log.history || [];   // store logs to an array for reference
  log.history.push(arguments);
  if(this.console) {
    arguments.callee = arguments.callee.caller;
    var newarr = [].slice.call(arguments);
    (typeof console.log === 'object' ? log.apply.call(console.log, console, newarr) : console.log.apply(console, newarr));
  }
};

// make it safe to use console.log always
(function(b){function c(){}for(var d="assert,count,debug,dir,dirxml,error,exception,group,groupCollapsed,groupEnd,info,log,timeStamp,profile,profileEnd,time,timeEnd,trace,warn".split(","),a;a=d.pop();){b[a]=b[a]||c}})((function(){try
{console.log();return window.console;}catch(err){return window.console={};}})());


// place any jQuery/helper plugins in here, instead of separate, slower script files.

// https://flask-wtf.readthedocs.io/en/stable/csrf.html#setup
$.ajaxSetup({
    beforeSend: function(xhr, settings) {
        var csrf_token = $("input#csrf_token").val();
        if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
            xhr.setRequestHeader("X-CSRFToken", csrf_token);
        }
    }
});

// datepicker related see https://www.npmjs.com/package/jquery-datetimepicker -->
jQuery.datetimepicker.setLocale('en');
jQuery('.dtpick').datetimepicker({
  format:'Y-m-d H:i'
});
jQuery('.tpick').datetimepicker({
  datepicker:false,
  format:'H:i'
});

// clear advanced search fields
$(function () {
    $("input#reset-adv-search").click(function (event) {
        event.stopPropagation()
        event.preventDefault();
        $("input[name='name']").val("");
        $("input[name='city']").val("");
        $("select[name='state']").val("none");
        $("select[name='genres']").val("any");
    })
});

// delete entities
var delete_entity = function(name, href) {
    // name: entity name to display in confirmation
    // href: url for delete
    let result = confirm("Are you sure? This will permanently delete "+name.trim()+"!");
    if (result) {
        $.ajax({
            url: href,
            method: 'DELETE',
            contentType: false,
            success: function(result) {
                window.location.replace(result["redirect"]);
            }
        });
    }
}
// delete venue
$(function () {
    $("a#delete_venue").click(function (event) {
        event.stopPropagation()
        event.preventDefault();
        delete_entity($("span#venue_name_text").text(), $(this).attr("href"));
    })
});
// delete artist
$(function () {
    $("a#delete_artist").click(function (event) {
        event.stopPropagation()
        event.preventDefault();
        delete_entity($("span#artist_name_text").text(), $(this).attr("href"));
    })
});


// book show related functions
function matchDate(queryDate) {
    var matchedDate = null;
    if (queryDate != null) {
        var match = queryDate.match(/(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})/);
        if (match) {
            matchedDate = match[1] + " " + match[2]
        }
    }
    return matchedDate;
}

function entityIdFromUrl() {
    // get entity id from url                 http://  .....          /.../123
    const found = window.location.href.match(/\w+:\/\/[\w\d.]*[:]?\d*\/.*\/(\d+)/);
    var entityId = 0;
    if (found) {
        entityId = parseInt(found[1]);
    }
    return entityId;
}

function setClass(selector, className) {
    $(selector).attr("class", className)
}

function setArtistAvailabilityClasses(displayAvailabilityClass, noAvailabilityClass, availabilityNaClass) {
    $('div#display_availability').attr("class", displayAvailabilityClass)
    $('div#no_availability').attr("class", noAvailabilityClass)
    $('div#availability_na').attr("class", availabilityNaClass)
}

// get availability for selected artist
function getArtistAvailability(artistId, queryDate) {

    var match = matchDate(queryDate)

    if ((artistId > 0) && (match != null)) {

        $('div#availability').empty()

        fetch(encodeURI("/artists/"+artistId+"/availability?query_date="+match), {
            method: 'GET'
        })
        .then(response => response.json())
        .then(jsonResponse => {
            console.log(jsonResponse);

            const availability = jsonResponse['availability'];
            if (availability.length > 0) {
                availability.forEach(entry => {
                    const span = document.createElement('span');
                    span.className = 'available-slot';

                    const text = document.createTextNode(' ' + entry + ' ');
                    span.appendChild(text);

                    $('div#availability').append(span)
                });
                setArtistAvailabilityClasses("available-line", "hidden", "hidden")
            } else {
                setArtistAvailabilityClasses("hidden", "not-available-line", "hidden")
            }
        })
        .catch(() => {
            setArtistAvailabilityClasses("hidden", "hidden", "not-available-line")
        });
    } else {
        setArtistAvailabilityClasses("hidden", "hidden", "not-available-line")
    }
}

function setVenueBookingsClasses(displayBookingsClass, noBookingsClass, bookingsNaClass) {
    $('div#display_bookings').attr("class", displayBookingsClass)
    $('div#no_bookings').attr("class", noBookingsClass)
    $('div#bookings_na').attr("class", bookingsNaClass)
}

// get bookings for selected venue
function getVenueBookings(venueId, queryDate) {

    var match = matchDate(queryDate)

    if ((venueId > 0) && (match != null)) {

        $('div#bookings').empty()

        fetch(encodeURI("/venues/"+venueId+"/bookings?query_date="+match), {
            method: 'GET'
        })
        .then(response => response.json())
        .then(jsonResponse => {
            console.log(jsonResponse);

            const bookings = jsonResponse['bookings'];
            if (bookings.length > 0) {
                bookings.forEach(entry => {
                    const span = document.createElement('span');
                    span.className = 'available-slot';

                    const text = document.createTextNode(' ' + entry + ' ');
                    span.appendChild(text);

                    $('div#bookings').append(span);
                });
                setVenueBookingsClasses("available-line", "hidden", "hidden")
            } else {
                setVenueBookingsClasses("hidden", "not-available-line", "hidden")
            }
        })
        .catch(() => {
            setVenueBookingsClasses("hidden", "hidden", "not-available-line")
        });
    } else {
            setVenueBookingsClasses("hidden", "hidden", "not-available-line")
    }
}

const dowIds = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat']
function setDowIndicator(startTime) {
    $(".dow-day").attr("class", "dow")
    date = new Date(startTime)
    $("span#"+dowIds[date.getDay()]).attr("class", "dow-day")
}

$(function () {
    // update availability for selected artist on edit show page
    $("select#artist_id").change(function (event) {
        event.stopPropagation()
        event.preventDefault();
        getArtistAvailability(parseInt($(this).val()), $("input#start_time").val());
    })

    // update bookings for selected venue and availability for selected artist on edit show page
    $("input#start_time").change(function (event) {
        event.preventDefault();

        // when editing the datetime field manually, 2 events are produced, the
        // standard html event and a jquery event
        // TODO better way to distinguish between html & jquery events
        if (typeof(event.isTrigger) == 'number') {
            // jquery event, handle this as received for both key and mouse
            const startTime = $(this).val();
            setDowIndicator(startTime);

            var venueId;
            if ($('select#venue_id').length) {
                // edit_show
                venueId = parseInt($('select#venue_id').val());
            } else {
                venueId = entityIdFromUrl();
            }
            getVenueBookings(venueId, startTime);

            getArtistAvailability(parseInt($('select#artist_id').val()), startTime);
        }
    });

    // update bookings for selected venue on edit show page
    $("select#venue_id").change(function (event) {
        event.stopPropagation()
        event.preventDefault();
        getVenueBookings(parseInt($(this).val()), $("input#start_time").val());
    });

    // save selected artist for booking on show venue page
    // thanks to https://stackoverflow.com/a/43259496
    $(function () {
        $(".booking-btn").click(function () {
            var artist_id = $(this).data('artist_id');
            $(".modal-body #booking_artist_id").val(artist_id);
        })
    });

    // transfer to list a show from show venue page
    $(function () {
        $("a#do-booking").click(function () {
            const artist_id = $(".modal-body #booking_artist_id").val();
            const venue_id = entityIdFromUrl();
            const start_time = $("input#start_time").val()

            url = $(this).attr("href")
            url = url.replace('<artist_id>', artist_id)
            url = url.replace('<venue_id>', venue_id)
            url = url.replace('<starttime>', start_time)
            url = $(this).attr("href", url)
        })
    });
});

window.onload = function() {
    // set dow indicator on edit-show & show-venue
    const startTime = $("input#start_time").val();
    if (startTime != null) {
        setDowIndicator(startTime);
    }

    if ($("p#page-title").text() == "edit-show") {
        // load info for selections on edit show page
        getArtistAvailability($("select#artist_id").val(), startTime);
        getVenueBookings(parseInt($('select#venue_id').val()), startTime);
    }
};

