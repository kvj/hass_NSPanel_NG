#pragma once

#include "esphome/core/component.h"
#include "esphome/core/application.h"
#include "esphome/components/rtttl/rtttl.h"
#include "esphome/components/nextion/nextion.h"
#include "esphome/components/switch/switch.h"
#include "esphome/components/binary_sensor/binary_sensor.h"
#include "esphome/components/api/api_server.h"

#define NS_PANEL_NG_VER "0.1.3"


namespace esphome {
namespace nspanel_ng {

static std::vector<std::string> all_grid_cmps = {"grid_bg", "grid_hs", "grid_b_icon", "grid_b_name", "grid_e_icon", "grid_e_name", "grid_e_value", "grid_e_unit"};
static std::vector<std::string> button_grid_cmps = {"grid_bg", "grid_b_icon", "grid_b_name", "grid_hs"};
static std::vector<std::string> entity_grid_cmps = {"grid_bg", "grid_e_icon", "grid_e_name", "grid_e_value", "grid_e_unit", "grid_hs"};

#define CT_PRESS 0
#define CT_RELEASE 1
#define CT_PENDING 2

#define CT_LONG_PRESS 800
#define CT_DOUBLE_DELAY 150

#define CT_NONE 0
#define CT_CLICK 1
#define CT_DOUBLE_CLICK 2
#define CT_LONG_CLICK 3

#define TFT_UPDATE_DELAY 15000

struct ClickTracker {
    uint32_t action_ts;
    uint8_t  clicks;
    uint8_t  next_state;
};

class NSPanelNG : public esphome::Component, public esphome::nextion::NextionComponentBase {

    private:
        esphome::rtttl::Rtttl *rtttl_player;
        esphome::nextion::Nextion *display;
        esphome::switch_::Switch *relay1, *relay2;
        esphome::binary_sensor::BinarySensor *button1, *button2;
        esphome::api::APIServer *api_server;
        float brightness_ = 1.0;
        float off_brightness_ = 0.01;
        std::map<int, std::string> cell_types = {{0, ""}, {1, ""}, {2, ""}, {3, ""}, {4, ""}, {5, ""}, {6, ""}, {7, ""}};
        std::vector<ClickTracker> clicks;
        std::string display_version_ = "Disconnected";
        std::string display_variant_;
        bool visual_feeback = true;
        bool sound_feedback = false;
        std::string tft_url;
        long tft_update_start = -1;
        int center_icon_visibility = 0;
        uint32_t center_icon_blink_start = 0;
        int last_pixels_size = 0;

    public:

        void set_display(esphome::nextion::Nextion *display) { 
            this->display = display; 
            display->register_textsensor_component(this);
        }
        void set_api_server(esphome::api::APIServer *api_server) { this->api_server = api_server; }
        void set_relays(esphome::switch_::Switch *relay1, esphome::switch_::Switch *relay2) {
            this->relay1 = relay1; 
            this->relay2 = relay2;
        }
        void set_buttons(esphome::binary_sensor::BinarySensor *button1, esphome::binary_sensor::BinarySensor *button2) {
            this->button1 = button1;
            this->button2 = button2;
        }
        void set_variant(const std::string variant) { this->display_variant_ = variant; }
        void set_rtttl_player(esphome::rtttl::Rtttl *rtttl_) { this->rtttl_player = rtttl_; }

        void setup() override;
        void loop() override;
        void process_text(const std::string &name, const std::string &value) override;
        void update_relay(const int index, const bool state);
        void update_backlight(const int value, const int off_value);
        void send_metadata();
        void upload_tft(const std::string path);
        void update_grid_cell(const int index, const std::string type_, const int icon, const std::string name, const std::string value, const std::string unit, const int color);
        void update_text(const int index, const std::string content, const int icon, const int color);
        void update_center_icon(const int icon, const int color, const int visibility);
        void play_sound(const std::string rtttl_content);
        void update_pixels(const std::vector<int> pixels);

    private:
        bool update_grid_visibility(const int index, const std::string type_, const bool force=false);
        const std::string gen_id(std::string prefix, int index);
        const std::string gen_icon_char(int icon);
        void send_hass_event(const std::string name, std::map<std::string, std::string> extra);
        void track_click(int index, bool press);
        uint8_t compute_click(int index);
        float _brightness_adjusted() { return brightness_ == 0? off_brightness_: brightness_; }
        void play_click_sound();
};

}
}
