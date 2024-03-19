#include "nspanel_ng.h"

namespace esphome {
namespace nspanel_ng {

namespace espbt = esphome::esp32_ble_tracker;
namespace espbs = esphome::esp32_ble_server;


void NSPanelNG::setup() {
    for (int i = 0; i < 14; i++) {
        this->clicks.push_back(ClickTracker {
            action_ts: 0,
            clicks: 0,
            next_state: CT_PENDING,
        });
    }
    display->add_setup_state_callback([this]() {
        ESP_LOGD("ng", "Setup state changed...");
    });
    // display->add_wake_state_callback([this]() {
    //     ESP_LOGD("ng", "Woken up...");
    //     this->update_grid_layout();
    // });
    relay1->add_on_state_callback([this](bool state) {
        ESP_LOGD("ng", "Relay 1, %d", state);
    });
    relay2->add_on_state_callback([this](bool state) {
        ESP_LOGD("ng", "Relay 2, %d", state);
    });
    button1->add_on_state_callback([this](bool state) {
        ESP_LOGD("ng", "Button 1, %d", state);
        this->track_click(12, state);
    });
    button2->add_on_state_callback([this](bool state) {
        ESP_LOGD("ng", "Button 2, %d", state);
        this->track_click(13, state);
    });
    display->add_raw_touch_event_callback([this](uint16_t x, uint16_t y, bool press) {
        this->process_touch(x, y, press);
    });
    display->register_textsensor_component(this);
}

void NSPanelNG::process_text(const std::string &name, const std::string &value) {
    ESP_LOGD("ng", "process_text: %s = %s", name.c_str(), value.c_str());
    if (name == "event") {
        DynamicJsonDocument doc(1024);
        deserializeJson(doc, value);
        // if ((doc["area"] == "bottom") && (brightness_ == 0)) {
        //     std::map<std::string, std::string> map;
        //     map["type"] = "wake";
        //     this->send_hass_event("Device_Event", map);
        // }
        // if (doc["area"] == "grid") {
        //     int cell = doc["cell"];
        //     if (doc["type"] == "press") {
        //         if (visual_feeback)
        //             display->set_backlight_brightness(0.2);
        //         track_click(cell, true);
        //     }
        //     if (doc["type"] == "release") {
        //         if (visual_feeback)
        //             display->set_backlight_brightness(_brightness_adjusted());
        //         track_click(cell, false);
        //     }
        // }
        if (doc["type"] == "startup") {
            this->display_version_ = (const char *)doc["version"];
        }
    }
}

void NSPanelNG::update_relay(const int index, const bool state) {
    ESP_LOGD("ng", "update_relay[%d]: %d", index, state);
    auto relay = index == 0? relay1: relay2;
    if (state) {
        relay->turn_on();
    } else {
        relay->turn_off();
    }
}

void NSPanelNG::update_backlight(const int value, const int off_value) {
    ESP_LOGD("ng", "update_backlight: %d / %d", value, off_value);
    brightness_ = value / 255.0;
    off_brightness_  = off_value / 100.0;
    display->set_backlight_brightness(_brightness_adjusted());
}

void NSPanelNG::send_metadata() {
    ESP_LOGD("ng", "send_metadata: %s / %s / %s", NS_PANEL_NG_VER, display_version_.c_str(), display_variant_.c_str());
    std::map<std::string, std::string> map;
    map["type"] = "metadata";
    map["component_version"] = NS_PANEL_NG_VER;
    map["display_version"] = display_version_;
    map["display_type"] = display_variant_;
    this->send_hass_event("Device_Event", map);
}

void NSPanelNG::upload_tft(const std::string path) {
    ESP_LOGD("ng", "upload_tft: via %s", path.c_str());
    if (tft_update_start == -1) {
        // display->set_tft_url(path);
        // display->write_str("DRAKJHSUYDGBNCJHGJKSHBDN");
        // const uint8_t to_send[3] = {0xFF, 0xFF, 0xFF};
        // display->write_array(to_send, sizeof(to_send));
        tft_url = path;
        tft_update_start = millis();
        ESP_LOGI("ng", "upload_tft: Scheduled upload via %s", path.c_str());
    } else {
        ESP_LOGW("ng", "upload_tft: Already scheduled");
    }
}

void NSPanelNG::update_grid_cell(const int index, const std::string type_, const int icon, const std::string name, const std::string value, const std::string unit, const int color) {
    ESP_LOGD("ng", "update_grid_cell[%d]: %s, %d, %s, %d", index, type_.c_str(), icon, name.c_str(), color);
    // if (type_ == "button") {
    //     display->set_component_font_color(this->gen_id("grid_b_icon", index).c_str(), color);
    //     display->set_component_text_printf(this->gen_id("grid_b_icon", index).c_str(), this->gen_icon_char(icon).c_str());
    //     display->set_component_text(this->gen_id("grid_b_name", index).c_str(), name.c_str());
    // }
    // if (type_ == "entity") {
    //     display->set_component_font_color(this->gen_id("grid_e_icon", index).c_str(), color);
    //     display->set_component_text_printf(this->gen_id("grid_e_icon", index).c_str(), this->gen_icon_char(icon).c_str());
    //     display->set_component_text(this->gen_id("grid_e_name", index).c_str(), name.c_str());
    //     display->set_component_text(this->gen_id("grid_e_value", index).c_str(), value.c_str());
    //     display->set_component_text(this->gen_id("grid_e_unit", index).c_str(), unit.c_str());
    // }
}

const std::string NSPanelNG::gen_icon_char(int icon) {
    unsigned char c1 = 224, c2 = 128, c3 = 128;
    for (int k=0; k<16; ++k) {
        if (k < 6)
            c3 |= (icon % 64) & (1 << k);
        else if (k < 12) 
            c2 |= (icon >> 6) & (1 << (k - 6));
        else
            c1 |= (icon >> 12) & (1 << (k - 12));
    }
    std::string s;
    s = c1;
    s += c2;
    s += c3;
    return s;
}

void NSPanelNG::send_hass_event(const std::string name, std::map<std::string, std::string> extra) {
    esphome::api::HomeassistantServiceResponse resp;
    resp.service = "esphome.NSPanel_NG_"+name;
    resp.is_event = true;
    esphome::api::HomeassistantServiceMap device_;
    device_.key = "device";
    device_.value = esphome::App.get_name();
    resp.data.push_back(device_);
    for (auto &it: extra) {
        esphome::api::HomeassistantServiceMap item_;
        item_.key = it.first;
        item_.value = it.second;
        resp.data.push_back(item_);
    }
    this->api_server->send_homeassistant_service_call(resp);
}

void NSPanelNG::track_click(int index, bool press) {
    if (press) {

        // Press - save when pressed and state
        clicks[index].next_state = CT_RELEASE; // Expect release
        clicks[index].action_ts = millis();
        // ESP_LOGD("ns", "track_click(): Record press for: %d", index);

    } else {

        // Only we actually expect release
        if (clicks[index].next_state == CT_RELEASE) {
            clicks[index].next_state = CT_PRESS;
            clicks[index].action_ts = millis();
            clicks[index].clicks += 1;
            // ESP_LOGD("ns", "track_click(): Record release for: %d", index);
        }

    }
}

uint8_t NSPanelNG::compute_click(int index) {
    uint32_t duration = millis() - clicks[index].action_ts;
    if (clicks[index].next_state == CT_PRESS) {
        // ESP_LOGD("ns", "compute_click(): Expect press for: %d", duration);
        if (duration >= CT_DOUBLE_DELAY) {

            // Delay between clicks is too long - report as single/double click
            clicks[index].next_state = CT_PENDING;
            auto clicks_ = clicks[index].clicks;
            if (clicks_ > 0) {
                clicks[index].clicks = 0;
                return clicks_ == 1? CT_CLICK: CT_DOUBLE_CLICK;
            }
        }
    }
    if (clicks[index].next_state == CT_RELEASE) {
        // ESP_LOGD("ns", "compute_click(): Expect release for: %d", duration);
        if (duration >= CT_LONG_PRESS) {

            // Pressed for too long - report as long click
            clicks[index].next_state = CT_PENDING;
            clicks[index].clicks = 0;
            return CT_LONG_CLICK;
        }
    }
    return CT_NONE;
}

void NSPanelNG::loop() {
    EasyBLEServer::loop();
    for (int i = 0; i < 14; i++) {
        uint8_t click_result = compute_click(i);
        if (click_result == CT_NONE) continue;
        std::string mode = "single";
        switch (click_result) {
            case CT_DOUBLE_CLICK:
                mode = "double"; break;
            case CT_LONG_CLICK:
                mode = "long"; break;
        }
        ESP_LOGD("ns", "loop(): Report click: [%d] %s", i, mode.c_str());
        std::map<std::string, std::string> map;
        map["mode"] = mode;
        if (i < 12) {
            map["type"] = "grid_click";
            map["cell"] = std::to_string(i);
        } else {
            map["type"] = "button_click";
            map["index"] = std::to_string(i-12);
        }
        this->send_hass_event("Device_Event", map);
    }
    if (tft_update_start != -1) {
        // if (millis() - tft_update_start >= TFT_UPDATE_DELAY) {
            tft_update_start = -1;
            ESP_LOGI("ng", "Starting TFT Upload: %s", tft_url.c_str());
            display->set_tft_url(tft_url);
            display->upload_tft();
        // }
    }
    if (pixels_screensaver_ && (esphome::millis() - pixels_screensaver_change_ts_ > SCREENSAVER_CHANGE_MS)) {
        update_screensaver(true, 0);
    }
    if (center_icon_blink_start > 0) {
        bool flip = (millis() - center_icon_blink_start) >= abs(center_icon_visibility);
        if (flip) {
            center_icon_visibility = -center_icon_visibility;
            center_icon_blink_start = millis();
            if (center_icon_visibility < 0)
                display->hide_component("bottom_icon");
            else
                display->show_component("bottom_icon");
        }
    }
}

void NSPanelNG::update_text(const int index, const std::string content, const int icon, const int color) {
    ESP_LOGD("ng", "update_text[%d]: %s", index, content.c_str());
    if (icon > 0) {
        // display->hide_component(this->gen_id("bottom_text", index).c_str());
        // display->set_component_font_color(this->gen_id("bottom_icon", index).c_str(), color);
        // display->set_component_text_printf(this->gen_id("bottom_icon", index).c_str(), this->gen_icon_char(icon).c_str());
        // display->show_component(this->gen_id("bottom_icon", index).c_str());
    } else {
        // display->hide_component(this->gen_id("bottom_icon", index).c_str());
        // display->set_component_text(this->gen_id("bottom_text", index).c_str(), content.c_str());
        // display->show_component(this->gen_id("bottom_text", index).c_str());
    }
}

void NSPanelNG::update_center_icon(const int icon, const int color, const int visibility) {
    ESP_LOGD("ng", "update_center_icon: icon: %d color: %d  visibility: %d", icon, color, visibility);
    center_icon_visibility = visibility;
    center_icon_blink_start = 0;
    if (visibility == 0) {
        // display->hide_component("bottom_icon");
    } else {
        // display->set_component_font_color("bottom_icon", color);
        // display->set_component_text_printf("bottom_icon", this->gen_icon_char(icon).c_str());
        // display->show_component("bottom_icon");
        // if (visibility > 0) {
        //     center_icon_blink_start = millis();
        // }
    }
}

void NSPanelNG::play_sound(const std::string rtttl_content) {
    ESP_LOGD("ng", "play_sound: %s", rtttl_content.c_str());
    rtttl_player->play(rtttl_content);
}

#define CELL_WIDTH 110
#define CELL_HEIGHT 110
#define CELL_GAP 5
#define CELL_COUNT 12
#define NO_TAG 0xff

#define AREA_WIDTH 440
#define AREA_HEIGHT 330

#define PIXELS_GAP 2

#define BUTTON_LABEL_HEIGHT 25

#define STYLE_BG_COLOR 4226
#define STYLE_TOUCH_COLOR 0xff292929

void NSPanelNG::draw_pixels(uint16_t x, uint16_t y, uint16_t w, bool clear) {
    auto bgColor = esphome::display::ColorUtil::to_color(
        STYLE_BG_COLOR, 
        esphome::display::ColorOrder::COLOR_ORDER_RGB, 
        esphome::display::ColorBitness::COLOR_BITNESS_565
    );
    if (clear) {
        display->fill_area(x, y, w, w, bgColor);
    }
    float size = sqrt(pixels_.size());
    int pixel_size = floor(w / size);
    int gap = PIXELS_GAP;
    for (int i = 0; i < size; i++) {
        for (int j = 0; j < size; j++) {
            auto color = pixels_[i * size + j] == -1? bgColor : esphome::display::ColorUtil::to_color(pixels_[i * size + j], esphome::display::ColorOrder::COLOR_ORDER_RGB, esphome::display::ColorBitness::COLOR_BITNESS_565);
            display->fill_area(x + j * (pixel_size), y + i * (pixel_size), pixel_size - gap, pixel_size - gap, color);
        }
    }
}

void NSPanelNG::update_pixels(uint8_t tag, const std::vector<int> pixels) {
    ESP_LOGD("ng", "update_pixels(): size = %d", pixels.size());
    this->pixels_.clear();
    if (pixels.size() == 0) {
        ESP_LOGW("ng", "No pixels provided, exiting");
        return;
    }

    float size = sqrt(pixels.size());
    if (floor(size) != size) {
        ESP_LOGW("ng", "Pixels aren't square, exiting");
        return;
    }
    this->pixels_.insert(this->pixels_.end(), pixels.begin(), pixels.end());
    pixels_tag_ = tag;

    std::vector<uint8_t> ble_data = {};
    ble_data.push_back(tag);
    for (auto &it : pixels) {
        ble_data.push_back(it); ble_data.push_back(it >> 8);
    }
    ble_write_char(BLE_SERVICE, BLE_CHR_MAP, ble_data, true);

    bool clear = false;
    if (last_pixels_size != (int)size) {
        ESP_LOGD("ng", "update_pixels(): clearing up area");
        last_pixels_size = size;
        clear = true;
    }

    if (pixels_screensaver_) {
        draw_pixels(pixels_screensaver_dim_[0], pixels_screensaver_dim_[1], pixels_screensaver_dim_[2], clear);
        return;
    }

    auto geom = calc_geometry(tag);
    uint16_t x = geom.x + CELL_GAP;
    uint16_t y = geom.y + CELL_GAP;
    uint16_t w = std::min(geom.w, geom.h) - CELL_GAP * 2;

    draw_pixels(x, y, w, clear);
}

esphome::Color from_565(uint16_t color) {
    return esphome::display::ColorUtil::to_color(color, esphome::display::ColorOrder::COLOR_ORDER_RGB, esphome::display::ColorBitness::COLOR_BITNESS_565);
}

void NSPanelNG::update_layout(std::vector<int> layout) {
    for (uint8_t i = 0; i < CELL_COUNT; i++) {
        cell_to_tag[i] = NO_TAG;
    }
    tag_to_cells.clear();
    tag_content.clear();
    for (uint8_t i = 0; i < layout.size(); i++) {
        ESP_LOGD("ng", "update_layout() cell %d -> tag %d", i, layout[i]);
        cell_to_tag[i] = layout[i];
        if (auto search = tag_to_cells.find(layout[i]); search != tag_to_cells.end()) {
            search->second.push_back(i);
        } else {
            tag_to_cells[layout[i]] = {i};
        }
    }
    display->send_command_printf("cls %d", STYLE_BG_COLOR);
}

void NSPanelNG::update_cell(uint8_t tag, CellContent content) {
    tag_content[tag] = content;
    if (!pixels_screensaver_)
        render_cell(tag, false, esphome::Color::BLACK);
}

TagGeometry NSPanelNG::calc_geometry(uint8_t tag) {
    uint8_t cells_in_row = floor(AREA_WIDTH / CELL_WIDTH);
    if (auto search = tag_to_cells.find(tag); search != tag_to_cells.end()) {
        auto cells = search->second;
        uint8_t last_cell = cells[0];
        uint16_t x = (cells[0] % cells_in_row) * CELL_WIDTH;
        uint16_t y = floor(cells[0] / cells_in_row) * CELL_HEIGHT;
        uint16_t w = CELL_WIDTH;
        uint16_t h = CELL_HEIGHT;
        for (uint8_t i = 1; i < cells.size(); i++) {
            if(cells[i] == last_cell+1) {
                w += CELL_WIDTH;
                last_cell = cells[i];
            }
        }
        return TagGeometry {
            x: x,
            y: y,
            w: w,
            h: h,
        };
    }
    return TagGeometry {
        x: 0,
        y: 0,
        w: 1,
        h: 1,
    };
}

void NSPanelNG::render_cell(uint8_t tag, bool with_bg, esphome::Color bg_color) {
    if (auto search = tag_content.find(tag); search != tag_content.end()) {
        auto content = search->second;
        auto geom = calc_geometry(tag);
        ESP_LOGD("ng", "render_cell() type = %s, x = %d, y = %d, w = %d, h = %d", content.type.c_str(), geom.x, geom.y, geom.w, geom.h);
        uint16_t x = geom.x + CELL_GAP;
        uint16_t y = geom.y + CELL_GAP;
        uint16_t w = geom.w - CELL_GAP * 2;
        uint16_t h = geom.h - CELL_GAP * 2;
        auto fg_color = from_565(content.color);
        auto bg_color = from_565(content.bg_color);
        // display->send_command_printf("com_stop");
        if (content.type == "hidden") {
            display->fill_area(geom.x, geom.y, geom.w, geom.h, from_565(STYLE_BG_COLOR));
        }
        if (content.type == "text") {
            if (content.icon > 0) {
                nextion_xstr(
                    x, y, w, h,
                    4,
                    fg_color, bg_color,
                    1,
                    gen_icon_char(content.icon)
                );
            } else {
                nextion_xstr(
                    x, y, w, h,
                    2,
                    fg_color, bg_color,
                    1,
                    content.label
                );
            }
        }
        if (content.type == "icon") {
            uint16_t icon_height = geom.h - CELL_GAP * 2;
            if (content.label != "") {
                nextion_xstr(
                    x,
                    geom.y + geom.h - CELL_GAP * 2 - BUTTON_LABEL_HEIGHT,
                    w,
                    BUTTON_LABEL_HEIGHT,
                    0,
                    fg_color, bg_color,
                    1,
                    content.label
                );
                icon_height -= BUTTON_LABEL_HEIGHT;
            }
            nextion_xstr(
                x, y, w,
                icon_height,
                4,
                fg_color, bg_color,
                1,
                gen_icon_char(content.icon)
            );
        }
        if (content.type == "button") {
            if (with_bg) {
                bg_color = bg_color.darken(0x20);
                fg_color = fg_color.darken(0x20);
            }
            // display->fill_area(
            //     x, y, w, h,
            //     bg_color
            // );
            if (content.icon > 0) {
                uint16_t icon_height = geom.h - CELL_GAP * 2;
                if (content.label != "") {
                    nextion_xstr(
                        x,
                        geom.y + geom.h - CELL_GAP * 2 - BUTTON_LABEL_HEIGHT,
                        w,
                        BUTTON_LABEL_HEIGHT,
                        0,
                        fg_color, bg_color,
                        1,
                        content.label
                    );
                    icon_height -= BUTTON_LABEL_HEIGHT;
                }
                nextion_xstr(
                    x, y, w,
                    icon_height,
                    4,
                    fg_color, bg_color,
                    1,
                    gen_icon_char(content.icon)
                );
            } else {
                nextion_xstr(
                    geom.x + CELL_GAP, 
                    geom.y + CELL_GAP, 
                    geom.w - CELL_GAP * 2, 
                    geom.h - CELL_GAP * 2, 
                    0,
                    fg_color, bg_color,
                    1,
                    content.label
                );
            }
        }
        // display->send_command_printf("com_start");
    } else {
        ESP_LOGW("ng", "render_cell(): No content for tag: %d", tag);
    }

}

void NSPanelNG::nextion_xstr(uint16_t x, uint16_t y, uint16_t w, u_int16_t h, uint8_t font, esphome::Color color, esphome::Color bg_color, uint8_t ha, std::string text) {
    display->send_command_printf(
        "xstr %d,%d,%d,%d,%d,%d,%d,%d,%d,%d,\"%s\"", 
        x, y, w, h, font, 
        esphome::display::ColorUtil::color_to_565(color), 
        esphome::display::ColorUtil::color_to_565(bg_color),
        ha, 1,
        1,
        text.c_str()
    );
}


void NSPanelNG::process_touch(uint16_t x, uint16_t y, bool on) {
    ESP_LOGD("ng", "process_touch(): %dx%dx%d", x, y, on);
    if (pixels_screensaver_) {
        update_screensaver(false, 0);

        std::map<std::string, std::string> map;
        map["type"] = "screensaver";
        map["is_on"] = "false";
        this->send_hass_event("Device_Event", map);

        return;
    }
    uint8_t cell_x = floor(x / CELL_WIDTH);
    uint8_t cell_y = float(y / CELL_HEIGHT);
    uint8_t cells_in_row = floor(AREA_WIDTH / CELL_WIDTH);
    uint8_t cell = cell_y * cells_in_row + cell_x;
    uint8_t tag = cell_to_tag[cell];
    ESP_LOGD("ng", "process_touch(): cell = %d , x = %d, y = %d, tag = %d", cell, cell_x, cell_y, tag);
    if (tag != NO_TAG) {
        if (auto search = tag_content.find(tag); (search != tag_content.end()) && (search->second.type == "button")) {
            if (on)
                render_cell(tag, true, esphome::Color(STYLE_TOUCH_COLOR));
            else
                render_cell(tag, false, esphome::Color::BLACK);
            track_click(tag, on);
        }
    }
}

void NSPanelNG::update_screensaver(const bool is_on, const int type) {
    display->send_command_printf("cls %d", STYLE_BG_COLOR);
    if (is_on) {
        pixels_screensaver_ = true;
        uint16_t pixels_w = floor(std::min(AREA_HEIGHT, AREA_WIDTH) * 0.8);
        pixels_screensaver_dim_[0] = floor((AREA_WIDTH - pixels_w) * random_float());
        pixels_screensaver_dim_[1] = floor((AREA_HEIGHT - pixels_w) * random_float());
        pixels_screensaver_dim_[2] = pixels_w;
        draw_pixels(pixels_screensaver_dim_[0], pixels_screensaver_dim_[1], pixels_screensaver_dim_[2], true);
        pixels_screensaver_change_ts_ = esphome::millis();
    } else {
        pixels_screensaver_ = false;
        for (const auto& [tag, content] : tag_content) {
            render_cell(tag, false, esphome::Color::BLACK);
        }
        update_pixels(pixels_tag_, pixels_);
    }
}

void EasyBLEServer::loop() {
    if (this->ble_server->is_running()) {
        if (!ble_setup_complete) {
            this->ble_create_services();
            ble_setup_complete = true;
        }
        this->ble_start_services();
    }
}

void EasyBLEServer::ble_create_services() {
    auto svc_id = espbt::ESPBTUUID::from_uint16(BLE_SERVICE);
    auto chr_id = espbt::ESPBTUUID::from_uint16(BLE_CHR_MAP);
    this->ble_server->create_service(svc_id, true);
    auto *svc = this->ble_server->get_service(svc_id);
    auto *chr = svc->create_characteristic(chr_id, espbs::BLECharacteristic::PROPERTY_READ | espbs::BLECharacteristic::PROPERTY_NOTIFY);
    chr->add_descriptor(new esphome::esp32_ble_server::BLE2902());
}

void EasyBLEServer::ble_start_services() {
    auto svc_id = espbt::ESPBTUUID::from_uint16(BLE_SERVICE);
    auto *svc = this->ble_server->get_service(svc_id);
    if (svc != nullptr) {
        if (svc->is_created() && !svc->is_running()) {
            ESP_LOGD("ng", "ble_start_services(): starting service: 0x%x", BLE_SERVICE);
            svc->start();
        }
    }
}

bool EasyBLEServer::ble_write_char(uint16_t svc_uuid, uint16_t chr_uuid, std::vector<uint8_t> data, bool notify) {
    auto *svc = this->ble_server->get_service(espbt::ESPBTUUID::from_uint16(svc_uuid));
    if (svc == nullptr) return false;
    auto *chr = svc->get_characteristic(chr_uuid);
    if (chr == nullptr) return false;
    std::string log_str = "";
    for (int i = 0; i < data.size(); i++) {
        char buf[3];
        sprintf(buf, "%02x ", data[i]);
        log_str.append(buf);
    }
    chr->set_value(data);
    ESP_LOGD("ng", "ble_write_char() 0x%x::0x%x [%d] %s", svc_uuid, chr_uuid, notify, log_str.c_str());
    if (notify && (this->ble_server->get_connected_client_count() == 0)) return false;
    if (notify)
        chr->notify(true);
    return true;
}


}
}
