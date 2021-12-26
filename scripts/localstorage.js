cookieSettingsName = "hbjson_settings";
settingsValidity = 5;	    // 5 days
settings = [{ name: "openbridges", "open": true }, { "map": { "zoom" : 6.5 } }, {"name": "masters", "open": true }, { "name": "peers", "open": true }];

// localStorage.setItem('theme', themeName);
// localStorage.getItem('theme', themeName);

var names = [];    

names["Andre"] = "André";
names["Francois"] = "François";
names["Herve"] = "Hervé";
names["Jerome"] = "Jérôme";
names["Jerôme"] = "Jérôme";
names["Stephane"] = "Stéphane";
names["Gerard"] = "Gérard";
names["Jean-Noel"] = "Jean-Noël";
names["Remi"] = "Rémi";
names["Clement"] = "Clément";
names["Frederic"] = "Frédéric";
names["Jeremy"] = "Jérémy";
names["Jean-Francois"] = "Jean-François";
names["Gregory"] = "Grégory";    
names["Anne-Cecile"] = "Anne-Cécile";
names["Mickael"] = "Mickaël";
names["Theophile"] = "Théophile";
names["Sebastien"] = "Sébastien";
names["Sbastien"] = "Sébastien";
names["Raphael"] = "Raphaël";
names["Cedric"] = "Cédric";
names["Rene"] = "René";
names["Nathanael"] = "Nathanaël";
names["Joel"] = "Joël";
names["Jeremie"] = "Jérémie";

String.prototype.capitalize = function (lower) {
    return (lower ? this.toLowerCase() : this).replace(/(?:^|\s|['`‘’.-])[^\x00-\x60^\x7B-\xDF](?!(\s|$))/g, function (a) {
        return a.toUpperCase();
    });
};

function createCookie(name, value, days) {
    var expires;

    if (days) {
        var date = new Date();
        date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
        expires = "; expires=" + date.toGMTString();
    } else {
        expires = "";
    }
    
    document.cookie = encodeURIComponent(name) + "=" + encodeURIComponent(value) + expires + "; path=/";
}

function readCookie(name) {
    var nameEQ = encodeURIComponent(name) + "=";
    var ca = document.cookie.split(';');
    for (var i = 0; i < ca.length; i++) {
        var c = ca[i];
        while (c.charAt(0) === ' ')
            c = c.substring(1, c.length);
        if (c.indexOf(nameEQ) === 0)
            return decodeURIComponent(c.substring(nameEQ.length, c.length));
    }
    return null;
}

function getTgTableState(name) {
    for(let i=0; i < settings.length; i++) {
        if (settings[i].name != null && settings[i].name == name)
            return settings[i];
    }

    return null;
}

function saveSettings() {
    themeSettings = document.documentElement.className;
    settings = [
        { "config": { "theme": themeSettings } },
        { "map": { "zoom" : (map != null) ? map.getZoom() : 6.5 } },
        { "name": "openbridges",    "open": $('#openbridges').is(':visible'), "colspan": $("#theadOpenbridges tr th").length }, 
        { "name": "masters",        "open": $('#masters').is(':visible'), "colspan": $("#theadMasters tr th").length }, 
        { "name": "peers",          "open": $('#peers').is(':visible'), "colspan": $("#theadPeers tr th").length }
    ];

    if (tgorder != null) {
        tgorder.forEach(tg => {
            var tgName = "tgId"+tg;
            var tgId = "hblink"+tg;
            if (document.getElementById(tgName) != null)
                settings.push({ "name": tgId, "open": $("#" + tgId).is(":visible"), "colspan": $("#" + tgName + " tr th").length });
        });
    }
    
    createCookie(cookieSettingsName, JSON.stringify(settings), settingsValidity);
}

function eraseCookie(name) {
    createCookie(name, "", -1);
}    

function adjustTheme() {
    if (themeSettings == "auto") {
        if (new Date().getHours() > 22) {
            if (document.documentElement.className != "theme-dark")
                document.documentElement.className = "theme-dark";
        }
        else {
            if (document.documentElement.className != "theme-light")
                document.documentElement.className = "theme-light";
        }
    }
}

function getConfigFromLocalStorage() {
    map = null;

    // retrieve settings
    if ((cookie = JSON.parse(readCookie(cookieSettingsName))) == null) {
        cookie = settings;
        createCookie(cookieSettingsName, JSON.stringify(settings), settingsValidity);
    }
    else    
        settings = cookie;

    themeSettings = "theme-dark";

    for(let i=0; i < settings.length; i++) {
        var tbs = settings[i];

        if (tbs.config) {
            themeSettings = tbs.config.theme;

            if (themeSettings == "auto")
                adjustTheme();
            else
                document.documentElement.className = themeSettings;
        }
        else {
            if (tbs.map) {
                currentZoom = tbs.map.zoom;
            }
            else {
                if (tbs.open) {
                    $("#"+tbs.name).show();                                                            
                    var count = tbs.colspan;
                    if (count == null)
                        count = 5;
                    $("#"+tbs.name).append("<tr><td class='infoline' colspan="+(count+1)+">Mise à jour en cours...</td></tr>");
                }
                else
                    $("#"+tbs.name).hide();
            }
        }
    }            
}
