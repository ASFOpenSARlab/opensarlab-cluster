
$(function() {

    function modal_handler(message, success, cancel) {

        $('#error-dialog .ajax-error').html(message);

        $('#error-dialog').off()

        $('#error-dialog').on("click", "button.btn-primary", function(e){
            $('#error-dialog').modal("hide");
            if (success) {
                success();
            }
        });

        $('#error-dialog').on("click", "button.btn-default", function(e){
            $('#error-dialog').modal("hide");
            if (cancel) {
                cancel();
            }
        });

        $('#error-dialog').modal("show");
    }

    // The class `fade` conflicts with another library and breaks the modal.
    // This will give a black backgrouns but at least the modal works.
    $('#error-dialog').removeClass('fade');

    $table = $('#groups-main-table');

    $table.DataTable();

    $table.on('change', '.group-checkbox', function(e) {

        e.stopPropagation()

        try {
            $this = $(this)
            user_name = $this.data("user");
            group_name = $this.data("group");
            change_to_checked = $this.children('input')[0].checked;
            console.log("User '" + user_name + "' has been updated for group '" + group_name + "' because 'checked' is " + change_to_checked);
            $this.data("order", "" + change_to_checked);
            this_data = {
                "user_name": user_name,
                "group_name": group_name,
                "change_to_checked": change_to_checked,
                "operation": "checked"
            }
            var jqxhr = $.post( "/hub/groups", this_data)
                .done(function() {
                    console.log("Success");
                })
                .fail(function(result) {
                    console.log("Error: ", result)
                    modal_handler("There was an error while checking a checkbox: <br/> " + result);
                })
        }
        catch(err) {
            modal_handler("There was an unusual error: <br/> " + err);
        }
    });

    $table.on('click', function(e) {

        $target = $(e.target)

        if ( $target.is('#new-add-group-button') ) {
            // This is a dropdown button. Don't stop the bubble.
            console.log("Clicked on new button..")
        }
        else if ( $target.is('#new-submit-button') ){  
            e.stopPropagation()
            try {

                this_data = {
                    "group_name": $('#new-name-select').val(),
                    "description": $('#new-description-select').val(),
                    "group_type": $('#new-group-type-select input:checked').val(),
                    "is_all_users": $('#new-is-all-users-select')[0].checked,
                    "is_enabled": $('#new-is-enabled-select')[0].checked,
                    "operation": "add_group"
                };

                console.log("Group is being added to DB table:" + this_data );

                var jqxhr = $.post( "/hub/groups", this_data)
                    .done(function() {
                        console.log("This should not be printed. Instead, the page should be reloaded server side.");
                    })
                    .fail(function(result) {
                        console.log("Error: ", result)
                        modal_handler("There was an error while adding a new group: " + result.responseText)
                    })

            }
            catch(err) {
                modal_handler("There was an unusual error: <br/> " + err);
            }
        }
        else if ( $target.is('.group-update-button') ) {
            e.stopPropagation()
            try {

                group_name = $target.data("group");

                this_data = {
                    "group_name": group_name,
                    "description": $('#'+group_name +'-description-select').val(),
                    "group_type": $('#'+group_name +'-group-type-select input:checked').val(),
                    "is_all_users": $('#'+group_name +'-is-all-users-select')[0].checked,
                    "is_enabled": $('#'+group_name +'-is-enabled-select')[0].checked,
                    "operation": "update_group"
                };

                console.log("Group is being updated to DB table:" + this_data );

                var jqxhr = $.post( "/hub/groups", this_data)
                    .done(function() {
                        console.log("This should not be printed. Instead, the page should be reloaded server side.");
                    })
                    .fail(function(result) {
                        console.log("Error: " + result)
                        modal_handler("There was an error while adding a group: <br/> " + result);
                    })
            }
            catch(err) {
                modal_handler("There was an unusual error: <br/> " + err);
            }
        }
        else if ( $target.is('.group-delete-button') ) {
            e.stopPropagation()
            try {

                group_name = $target.data("group");
                message = "Are you sure you want to delete the group '" + group_name + "'?";

                this_data = {
                    "group_name": group_name,
                    "operation": "delete_group"
                };

                modal_handler(message,
                    function(e){
                        this_data = {
                            "group_name": group_name,
                            "operation": "delete_group"
                        };
                        console.log("Group '" + group_name + "' is being deleted from DB table" )
                        var jqxhr = $.post( "/hub/groups", this_data)
                            .done(function(res) {
                                console.log("You should not be reading this. Instead, the page should be reloaded server side.");
                                console.log("However, if we get here we will jquery delete the column.")
                                el_th = 'th[data-group="' + group_name + '"]'
                                el_td = 'td[data-group="' + group_name + '"]'
                                console.log("Deleting: " + el_th + ' and ' + el_td)
                                $(el_th).remove();
                                $(el_td).remove();
                            })
                            .fail(function(result) {
                                console.log("Error: " + result)
                                modal_handler("There was an error while deleting a group:" + result);
                            })
                    },
                    function(e){
                        modal_handler("There was an unusual error: <br/> " + e);
                    }
                );
            }
            catch(err) {
                console.log(err)
                modal_handler("There was an unusual error: <br/> " + err);
            }
        }
        else if ( $target.is('th.sorting_asc') ) {
            e.stopPropagation()

            myIndex = $(e.target).prevAll().length;
            console.log("Sorting asc on index '" + myIndex + "'")
            $('#groups-main-table').DataTable().order([myIndex, "asc"]).draw()
        }
        else if ( $target.is('th.sorting_desc') ) {
            e.stopPropagation()

            myIndex = $(e.target).prevAll().length;
            console.log("Sorting desc on index '" + myIndex + "'")
            $('#groups-main-table').DataTable().order([myIndex, "desc"]).draw()
        }
        else if ( $target.is('th.sorting') ) {
            // Stop any bubbles for sorting that are not already captured.
            e.stopPropagation()
        }
        else if ( $target.is('span.h4') ) {
            // This may be a dropdown. Don't stop the bubble.
            console.log("Clicked on link...")
        }
        else {
            e.stopPropagation()
            console.log("Target evented: ", $target, ". Not bubbling up event.")
        }
    });

    console.log("Page loaded on " + new Date().toLocaleString());

});
