import { patch } from "@web/core/utils/patch";
import { localizationService } from "@web/core/l10n/localization_service";

/**
 * The shop's clock is a 24-hour one -- 20:31, never 8:31 PM -- wherever a time
 * is rendered from the *locale* rather than from the language's format.
 *
 * Odoo renders a datetime two different ways, and only one of them reads
 * `res.lang.time_format` (the data file beside this one sets it to %H:%M:%S):
 *
 *  * `formatDateTime(value, { numeric: true })` -- the datetime picker, a
 *    numeric form field -- formats with `localization.dateTimeFormat`, so the
 *    language's format decides and the data file is enough;
 *  * `toLocaleDateTimeString(value)` -- every list and kanban cell, and the POS
 *    receipt -- formats with `value.toLocaleString(DateTime.DATETIME_MED...)`,
 *    i.e. with luxon's *locale*, which no `time_format` can reach. The web
 *    client sets that locale from the language code (`Settings.defaultLocale =
 *    user.lang`, in @web/core/l10n/localization_service), and `en_US` is a
 *    12-hour locale: the cells read "Oct 16, 8:31 PM" whatever the language's
 *    format says. Verified on the live stack -- with `res.lang.time_format` set
 *    to %H:%M:%S, the Orders list still printed 8:31 PM.
 *
 * The Unicode extension `-u-hc-h23` is the one lever that reaches it: Intl
 * reads it as "hour cycle 0 through 23", so the same locale renders 20:31 while
 * its month names, date order and everything else stay en_US. It is applied
 * once, right after the localization service has set the locale, and only when
 * that locale does not already carry an extension of its own.
 *
 * `h23` and not `h24`: 0-23 is what a shop means by 24 hours -- h24 prints
 * midnight as 24:00.
 *
 * Patch of the service object itself rather than a second service: services
 * start lazily, and this one has to have run before any component formats a
 * date, so the format is set in the same call that chooses the locale.
 */
patch(localizationService, {
    async start() {
        const result = await super.start(...arguments);
        const { Settings } = luxon;
        const locale = Settings.defaultLocale;
        if (locale && !locale.includes("-u-")) {
            Settings.defaultLocale = `${locale}-u-hc-h23`;
        }
        return result;
    },
});
