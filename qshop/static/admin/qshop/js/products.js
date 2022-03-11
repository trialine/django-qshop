(function($) {
    $(function() {
        $('#producttoparameter_set-group .form-row').each(function(){
            id = $('.j_parameter_id', this).val();

            // add-link add hide_parameter
            add_link = $('a.add-related', this);
            add_link_href = add_link.attr('href');

            add_link.attr(
                'href',
                add_link_href + (add_link_href.indexOf('?')!= -1 ? '&' : '?') + 'parameter=' + id + '&hide_parameter'
            );



            // change-link add hide_parameter
            change_link = $('a.change-related', this);
            change_link_href = change_link.attr('href');

            href_template = change_link.data('href-template');
            href = $(this).attr('href');


            change_link.attr(
                'data-href-template',
                href_template + (href_template.indexOf('?')!= -1 ? '&' : '?') + 'parameter=' + id + '&hide_parameter');

            if(change_link_href)
                change_link.attr(
                    'href',
                    change_link_href + (change_link_href.indexOf('?')!= -1 ? '&' : '?') + 'parameter=' + id + '&hide_parameter');

            $(this).addClass( $(".j_colored-tr", this).data('class') )

        });


    });

})(jQuery);
