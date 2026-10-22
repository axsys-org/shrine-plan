//! Read-only validation using the actual goo-egui consumer, not a parallel schema.
use shrine_egui::{model::Context, transport::Client};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let server = std::env::var("GOO_SERVER").unwrap_or_else(|_| "http://127.0.0.1:8190".into());
    let client = Client::new(&server)?;
    let target = "/0x11/app/branchmap/exchange";
    for width in [480., 900., 1200.] {
        let context = Context::new(width);
        let presentation = client.render(target, "slot", "/sys/slot/content", &context)?;
        presentation.validate(&context, target)?;
        assert_eq!(presentation.seeds().len(), 6);
        assert_eq!(presentation.controls.iter().filter(|c| c.binding.kind == "invoke").count(), 1);
        println!("PASS: goo-egui admits Branchmap prepared view at width {width}");
    }
    Ok(())
}
