window.t = (key, vars = {}) => {
  let str = (window.TRANSLATIONS || {})[key] || key;
  Object.entries(vars).forEach(([k, v]) => {
    str = str.replaceAll(`{${k}}`, String(v));
  });
  return str;
};

window.TRANSLATIONS = {
  // chat.js
  "empty_chat_message": "No messages yet.",
  "anonymous_user_default": "Anon",

  // shared (discussions, new_post, edit_post, report_detail)
  "error_max_images_exceeded": "Maximum {maxFiles} images per submission.",
  "error_invalid_file_format": "Format not allowed: {ext}.",
  "error_image_too_large": "Each image must be <= {maxMb}MB.",
  "button_publishing": "Publishing...",
  "button_sending": "Sending...",
  "error_recaptcha_required": "Please complete the reCAPTCHA before submitting.",
  "label_image_caption_optional": "Short description (optional)",
  "label_image_caption_numbered": "Short description (image {idx})",
  "alt_image_preview": "Preview {idx}",

  // new_post.js / edit_post.js
  "label_choose_municipality": "Choose municipality",
  "error_location_outside_cuba": "The location must be within Cuban territory.",
  "error_image_required_for_residence": "You must upload at least one image of the repressor.",
  "error_otros_cannot_be_represor": "The type in Others cannot refer to repressors. Use the corresponding category.",
  "error_date_time_required": "You must specify the date and time of the event.",
  "placeholder_link_url": "Link URL",
  "placeholder_example_url": "https://example.com/source",

  // map.js
  "search_placeholder_1": "E.g.: PNR Sector",
  "search_placeholder_2": "E.g.: Prison",
  "search_placeholder_3": "E.g.: Military Unit",
  "search_placeholder_4": "E.g.: Troops",
  "search_placeholder_5": "E.g.: Police Station",
  "search_placeholder_6": "E.g.: Detention Center",
  "search_placeholder_7": "E.g.: Special Brigade",
  "button_show_filters": "Show filters",
  "button_hide_filters": "Hide filters",
  "map_layer_streets": "Map",
  "map_layer_satellite": "Satellite",
  "empty_recent_feed": "No contributions visible yet.",
  "empty_alerts_feed": "No recent movements, outages, or actions.",
  "label_not_data_unknown": "N/A",
  "button_view_on_map": "View on map",
  "dropdown_all_option": "All",
  "button_view_detail": "View detail",
  "button_copy_link": "Copy link",
  "toast_link_copied": "Link copied",
  "button_report_location": "Report location",
  "button_view_history": "View history",
  "button_verify": "Verify",
  "button_verified": "Verified",
  "message_edit_locked": "Edit locked: 10+ verifications. You can comment and report location if there are errors.",
  "button_edit": "Edit",
  "button_hide": "Hide",
  "button_delete": "Delete",
  "alt_report_image": "Report image",
  "message_pending_moderation": "Report submitted for moderation.",
  "message_will_show_when_approved": "It will appear once approved.",
  "confirmation_hide_report": "Hide this report?",
  "confirmation_delete_report": "Delete this report?",
  "heading_create_report_here": "Create report here",
  "button_open_form": "Open form",
  "marker_title_location": "Location",
  "marker_title_search": "Search",

  // push_alerts.js
  "status_alerts_unavailable": "Alerts unavailable",
  "status_notifications_disabled": "Notifications disabled on the server.",
  "button_install_pwa": "Install the PWA",
  "status_install_pwa_instructions": "To enable alerts you must install the PWA. iOS: Share → Add to Home Screen → open from icon. Android: Menu ⋮ → Install app / Add to Home Screen.",
  "status_push_not_supported": "Your browser does not support push notifications.",
  "button_disable_alerts": "Disable alerts",
  "status_alerts_active": "Alerts active for movements, outages, and repressive actions.",
  "button_alerts_blocked": "Alerts blocked",
  "status_enable_browser_notifications": "Enable notifications in your browser to continue.",
  "button_enable_alerts": "Enable alerts",
  "status_alert_categories": "Only for movements, outages, and repressive actions.",
  "error_notification_service_init": "Could not initialize the notification service.",
  "error_subscription_failed": "Could not register subscription.",
  "error_unsubscribe_failed": "Could not deactivate subscription.",

  // report_detail.js / reports.js
  "empty_comments": "No comments yet.",
  "confirmation_delete_comment": "Delete comment?",
  "fallback_copy_manual": "Copy manually",
  "error_recaptcha_loading": "reCAPTCHA is still loading. Please try again.",
  "error_comment_send_failed": "Could not send comment.",
  "status_uploading_images": "Uploading images...",
  "button_uploading": "Uploading...",
  "button_upload_images": "Upload images",
  "error_upload_failed": "Upload error.",
  "status_sent_to_moderation": "Sent to moderation.",
  "status_images_added": "Images added.",

  // analytics.js
  "error_analytics_load_failed": "Could not load analytics",
  "status_approved": "Approved",
  "status_pending": "Pending",
  "status_rejected": "Rejected",
  "status_hidden": "Hidden",
  "chart_label_report_comments": "Comments on reports",
  "chart_label_discussion_comments": "Comments on discussions",
  "button_loading": "Loading...",
  "button_refresh": "Refresh",
};
