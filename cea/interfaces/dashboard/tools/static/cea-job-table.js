/*jslint browser:true */
/*global $, Tabulator, io, console */

const JOB_STATES = ["pending", "started", "success", "error"];
const URL_LIST_JOBS = "../server/jobs/list";

let cea_job_table = null;

function update_job_state(job) {
    "use strict";

    console.log("updating job state for job", job);
    $.getJSON(URL_LIST_JOBS, null, function (jobs) {
        cea_job_table.replaceData(jobs);
    });
}

function show_job_output(job) {
    "use strict";

    console.log(job);
}

$(document).ready(function () {
    "use strict";

    $.getJSON(URL_LIST_JOBS, null, function (jobs) {
        cea_job_table = new Tabulator("#cea-job-table", {
            data: jobs,           //load row data from array
            layout: "fitColumns",      //fit columns to width of table
            responsiveLayout: "hide",  //hide columns that dont fit on the table
            tooltips: true,            //show tool tips on cells
            addRowPos: "top",          //when adding a new row, add it to the top of the table
            history: true,             //allow undo and redo actions on the table
            pagination: "local",       //paginate the data
            paginationSize: 7,         //allow 7 rows per page of data
            movableColumns: true,      //allow column order to be changed
            resizableRows: true,       //allow row order to be changed
            initialSort: [{column: "id", dir: "desc"}],
            columns: [                 //define the table columns
                {title: "id", field: "id"},
                {title: "Script", field: "script"},
                {title: "State", field: "state", formatter: (cell) => JOB_STATES[cell.getValue()]},
                {title: "Parameters", field: "parameters"}
            ],
            rowClick: (e, row) => show_job_output(row.getData())
        });

        // handle state changes in worker
        let socket = io.connect(`http://${document.domain}:${location.port}`);
        socket.on("cea-worker-success", update_job_state);
        socket.on("cea-worker-error", update_job_state);
        socket.on("cea-worker-started", update_job_state);
    });
});