#include "nspanel_ng.h"

namespace esphome {
namespace nspanel_ng {

void NSPanelNG::setup() {
    for (int i = 0; i < 10; i++) {
        this->clicks.push_back(ClickTracker {
            action_ts: 0,
            clicks: 0,
            next_state: CT_PENDING,
        });
    }
    // display->add_setup_state_callback([this]() {
    //     ESP_LOGD("ng", "Setup state changed...");
    // });
    // display->add_wake_state_callback([this]() {
    //     ESP_LOGD("ng", "Woken up...");
    //     this->update_grid_layout();
    // });
    display->add_new_page_callback([this](uint8_t page) {
        ESP_LOGD("ng", "Page changed, %d", page);
    });
    relay1->add_on_state_callback([this](bool state) {
        ESP_LOGD("ng", "Relay 1, %d", state);
    });
    relay2->add_on_state_callback([this](bool state) {
        ESP_LOGD("ng", "Relay 2, %d", state);
    });
    button1->add_on_state_callback([this](bool state) {
        ESP_LOGD("ng", "Button 1, %d", state);
        this->track_click(8, state);
    });
    button2->add_on_state_callback([this](bool state) {
        ESP_LOGD("ng", "Button 2, %d", state);
        this->track_click(9, state);
    });
}

void NSPanelNG::process_text(const std::string &name, const std::string &value) {
    ESP_LOGD("ng", "process_text: %s = %s", name.c_str(), value.c_str());
    if (name == "event") {
        DynamicJsonDocument doc(1024);
        deserializeJson(doc, value);
        if ((doc["area"] == "bottom") && (brightness_ == 0)) {
            std::map<std::string, std::string> map;
            map["type"] = "wake";
            this->send_hass_event("Device_Event", map);
        }
        if (doc["area"] == "grid") {
            int cell = doc["cell"];
            if (doc["type"] == "press") {
                if (visual_feeback)
                    display->set_backlight_brightness(0.2);
                track_click(cell, true);
            }
            if (doc["type"] == "release") {
                if (visual_feeback)
                    display->set_backlight_brightness(_brightness_adjusted());
                track_click(cell, false);
            }
        }
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
    this->update_grid_visibility(index, type_);
    if (type_ == "button") {
        display->set_component_font_color(this->gen_id("grid_b_icon", index).c_str(), color);
        display->set_component_text_printf(this->gen_id("grid_b_icon", index).c_str(), this->gen_icon_char(icon).c_str());
        display->set_component_text(this->gen_id("grid_b_name", index).c_str(), name.c_str());
    }
    if (type_ == "entity") {
        display->set_component_font_color(this->gen_id("grid_e_icon", index).c_str(), color);
        display->set_component_text_printf(this->gen_id("grid_e_icon", index).c_str(), this->gen_icon_char(icon).c_str());
        display->set_component_text(this->gen_id("grid_e_name", index).c_str(), name.c_str());
        display->set_component_text(this->gen_id("grid_e_value", index).c_str(), value.c_str());
        display->set_component_text(this->gen_id("grid_e_unit", index).c_str(), unit.c_str());
    }
}

bool NSPanelNG::update_grid_visibility(const int index, const std::string type_, const bool force) {
    if ((this->cell_types[index] == type_) && !force) {
        return false;
    }
    for (auto it: all_grid_cmps) {
        display->hide_component(this->gen_id(it, index).c_str());
    }
    // delay(50);
    if (type_ == "button") {
        for (auto it: button_grid_cmps) {
            display->show_component(this->gen_id(it, index).c_str());
        }
        // delay(50);
    }
    if (type_ == "entity") {
        for (auto it: entity_grid_cmps) {
            display->show_component(this->gen_id(it, index).c_str());
        }
        // delay(50);
    }
    this->cell_types[index] = type_;
    return true;
}

const std::string NSPanelNG::gen_id(std::string prefix, int index) {
    return prefix + "_" + std::to_string(index);
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
    for (int i = 0; i < 10; i++) {
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
        if (i < 8) {
            map["type"] = "grid_click";
            map["cell"] = std::to_string(i);
            if (sound_feedback)
                play_click_sound();
        } else {
            map["type"] = "button_click";
            map["index"] = std::to_string(i-8);
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

void NSPanelNG::play_click_sound() {
    rtttl_player->play("one_short:d=4,o=5,b=100:128c-1");
}

void NSPanelNG::update_text(const int index, const std::string content, const int icon, const int color) {
    ESP_LOGD("ng", "update_text[%d]: %s", index, content.c_str());
    if (icon > 0) {
        display->hide_component(this->gen_id("bottom_text", index).c_str());
        display->set_component_font_color(this->gen_id("bottom_icon", index).c_str(), color);
        display->set_component_text_printf(this->gen_id("bottom_icon", index).c_str(), this->gen_icon_char(icon).c_str());
        display->show_component(this->gen_id("bottom_icon", index).c_str());
    } else {
        display->hide_component(this->gen_id("bottom_icon", index).c_str());
        display->set_component_text(this->gen_id("bottom_text", index).c_str(), content.c_str());
        display->show_component(this->gen_id("bottom_text", index).c_str());
    }
}

void NSPanelNG::update_center_icon(const int icon, const int color, const int visibility) {
    ESP_LOGD("ng", "update_center_icon: icon: %d color: %d  visibility: %d", icon, color, visibility);
    center_icon_visibility = visibility;
    center_icon_blink_start = 0;
    if (visibility == 0) {
        display->hide_component("bottom_icon");
    } else {
        display->set_component_font_color("bottom_icon", color);
        display->set_component_text_printf("bottom_icon", this->gen_icon_char(icon).c_str());
        display->show_component("bottom_icon");
        if (visibility > 0) {
            center_icon_blink_start = millis();
        }
    }
}

void NSPanelNG::play_sound(const std::string rtttl_content) {
    ESP_LOGD("ng", "play_sound: %s", rtttl_content.c_str());
    rtttl_player->play(rtttl_content);
}

#define PIXELS_START_X 340
#define PIXELS_START_Y 120
#define PIXELS_SIZE 100.0
#define PIXELS_GAP 2

void NSPanelNG::update_pixels(const std::vector<int> pixels) {
    ESP_LOGD("ng", "update_pixels(): size = %d", pixels.size());
    if (pixels.size() == 0) {
        ESP_LOGW("ng", "No pixels provided, exiting");
        return;
    } 
    float size = sqrt(pixels.size());
    if (floor(size) != size) {
        ESP_LOGW("ng", "Pixels aren't square, exiting");
        return;
    }
    auto bgColor = esphome::display::ColorUtil::to_color(4226, esphome::display::ColorOrder::COLOR_ORDER_RGB, esphome::display::ColorBitness::COLOR_BITNESS_565);
    if (last_pixels_size != (int)size) {
        ESP_LOGD("ng", "update_pixels(): clearing up area");
        last_pixels_size = size;
        display->fill_area(PIXELS_START_X, PIXELS_START_Y, PIXELS_SIZE, PIXELS_SIZE, bgColor);
    }
    int pixel_size = floor(PIXELS_SIZE / size);
    int gap = PIXELS_GAP;
    for (int i = 0; i < size; i++) {
        for (int j = 0; j < size; j++) {
            auto color = pixels[i * size + j] == -1? bgColor : esphome::display::ColorUtil::to_color(pixels[i * size + j], esphome::display::ColorOrder::COLOR_ORDER_RGB, esphome::display::ColorBitness::COLOR_BITNESS_565);
            display->fill_area(PIXELS_START_X + j * (pixel_size), PIXELS_START_Y + i * (pixel_size), pixel_size - gap, pixel_size - gap, color);
        }
    }
}

}
}
