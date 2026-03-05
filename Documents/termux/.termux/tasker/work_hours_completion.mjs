import { readFile, writeFile, existsSync } from "node:fs";
import parse from "csv-simple-parser";

const current_date = new Date();
const current_year = new Date().getFullYear();
const current_mon = new Date().getMonth();

function transform_data(holidays, mon) {
  let mon_days = 0;
  let mon_days_passed = 0;

  for (let day = 1; day <= 31; day++) {
    const date = new Date(current_year, mon, day);
    date.setHours(date.getHours() + 4); // WTF
    const datestring_naive = `${current_year}-${`0${mon + 1}`.slice(-2)}-${`0${day}`.slice(-2)}`;
    const datestring = `${date.getUTCFullYear()}-${`0${date.getUTCMonth() + 1}`.slice(-2)}-${`0${date.getUTCDate()}`.slice(-2)}`;
    if (
      !(
        datestring in holidays ||
        date.getUTCDay() === 6 ||
        date.getUTCDay() === 0
      ) &&
      datestring === datestring_naive // Not all months have 31 days
    ) {
      mon_days += 1;
      if (date < current_date) {
        mon_days_passed += 1;
      }
    }
  }

  return [mon_days, mon_days_passed];
}

function compare_hours(days_in_mon__days_passed) {
  let actual_minutes = 0;
  readFile(
    process.env.STT_PATH ?? "stt_records_automatic.csv",
    "utf8",
    function readFileCallback(err, data) {
      if (!err) {
        const csv = parse(data, { header: true });
        for (const row of csv) {
          if (row["time started"] == undefined) {
            continue;
          }
          const start = new Date(row["time started"]);
          const duration_min = Number.parseInt(row["duration minutes"]);
          const activity = row["activity name"];
          if (
            activity === "Work" &&
            start.getFullYear() == current_year &&
            start.getMonth() === current_mon
          ) {
            actual_minutes += duration_min;
          }
        }
        console.log(
          `${actual_minutes / 60}/${days_in_mon__days_passed[0]}/${days_in_mon__days_passed[1]}`,
        );
        process.exit(0);
      }
      console.log(err);
      process.exit(1);
    },
  );
}

try {
  const saved_holidays_file = `saved-holidays-${current_year}.json`;

  readFile(saved_holidays_file, "utf8", function readFileCallback(err, data) {
    if (!err) {
      const holidays = JSON.parse(data); //now it an object
      compare_hours(transform_data(holidays, current_mon));
    }
  });

  if (!existsSync(saved_holidays_file)) {
    fetch(`https://openholidaysapi.org/PublicHolidays?countryIsoCode=LT&languageIsoCode=EN&validFrom=${current_year}-01-01&validTo=${current_year+1}-01-01`, {
      credentials: "omit",
      headers: {
        "User-Agent":
          "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0",
        Accept:
          "application/json",
      },
      method: "GET",
      mode: "cors",
    }).then((response) => {
      response.json().then((response) => {
        let holidays_converted = {}
        for (const holiday of response) {
          const holiday_date = holiday["startDate"]
          holidays_converted[holiday_date] = holiday_date
        }
        writeFile(
          saved_holidays_file,
          JSON.stringify(holidays_converted),
          "utf8",
          () => {},
        );
        compare_hours(transform_data(holidays_converted, current_mon));
      });
    });
  }
} catch (error) {
  // Ignore
  process.exit(1);
}

